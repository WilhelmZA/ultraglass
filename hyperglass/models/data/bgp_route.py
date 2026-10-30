"""Device-Agnostic Parsed Response Data Model."""

# Standard Library
import re
import typing as t
from contextlib import contextmanager
from contextvars import ContextVar
from ipaddress import ip_network

# Third Party
from pydantic import ValidationInfo, field_validator, model_validator

# Project
from hyperglass.state import use_state
from hyperglass.external.rpki import rpki_state, rpki_states
from hyperglass.external.ip_enrichment import TargetDetail

# Local
from ..main import HyperglassModel

WinningWeight = t.Literal["low", "high"]

# While set, BGPRoute leaves external RPKI validation to the enclosing table,
# which validates all of its routes in one batch.
_DEFER_RPKI: ContextVar[bool] = ContextVar("defer_rpki", default=False)


@contextmanager
def defer_rpki() -> t.Iterator[None]:
    """Defer external RPKI validation of routes built here to their BGPRouteTable."""
    token = _DEFER_RPKI.set(True)
    try:
        yield
    finally:
        _DEFER_RPKI.reset(token)


def _rpki_target(prefix: str, as_path: t.List[int], value: int) -> t.Union[t.Tuple[str, int], int]:
    """Return the (prefix, origin ASN) pair to validate externally, or the final state."""
    if len(as_path) == 0:
        # Internal route, i.e. AS_PATH length 0: RPKI Unknown.
        return 3
    try:
        net = ip_network(prefix)
    except ValueError:
        return 3
    # Only do external RPKI lookups for global prefixes.
    if not net.is_global:
        return value
    # Last ASN in path is the origin.
    return (prefix, as_path[-1])


class BGPRoute(HyperglassModel):
    """Post-parsed BGP route."""

    prefix: str
    active: bool
    age: int
    weight: int
    med: int
    local_preference: int
    as_path: t.List[int]
    communities: t.List[str]
    next_hop: str
    source_as: int
    source_rid: str
    peer_rid: str
    rpki_state: int
    filtered: bool = False

    # IP enrichment data (optional)
    next_hop_asn: t.Optional[str] = None
    next_hop_org: t.Optional[str] = None
    next_hop_country: t.Optional[str] = None

    @field_validator("communities")
    def validate_communities(cls, value):
        """Filter returned communities against configured policy.

        Actions:
            permit: only permit matches
            deny: only deny matches
            name: append friendly names to matching communities
        """

        (structured := use_state("params").structured)

        def _permit(comm):
            """Only allow matching patterns."""
            valid = False
            for pattern in structured.communities.items:
                if re.match(pattern, comm):
                    valid = True
                    break
            return valid

        def _deny(comm):
            """Allow any except matching patterns."""
            valid = True
            for pattern in structured.communities.items:
                if re.match(pattern, comm):
                    valid = False
                    break
            return valid

        def _name(comm):
            """Append a friendly name to a community when one is mapped."""
            if comm in structured.communities.names:
                return f"{comm},{structured.communities.names[comm]}"
            return comm

        if structured.communities.mode == "name":
            return [_name(c) for c in value]

        func_map = {"permit": _permit, "deny": _deny}
        func = func_map[structured.communities.mode]

        return [c for c in value if func(c)]

    @field_validator("rpki_state")
    def validate_rpki_state(cls, value, info: ValidationInfo):
        """If external RPKI validation is enabled, get validation state."""

        (structured := use_state("params").structured)

        if structured.rpki.mode == "router":
            # If router validation is enabled, return the value as-is.
            return value

        if structured.rpki.mode == "external":
            if _DEFER_RPKI.get():
                # The enclosing BGPRouteTable validates in one batch.
                return value
            # If external validation is enabled, validate the prefix & asn
            # with the configured RPKI backend.
            target = _rpki_target(info.data.get("prefix", ""), info.data.get("as_path", []), value)
            if isinstance(target, int):
                return target
            return rpki_state(
                prefix=target[0],
                asn=target[1],
                backend=structured.rpki.backend,
                rpki_server_url=structured.rpki.rpki_server_url,
            )

        return value

    @property
    def as_path_summary(self) -> str:
        """Summary of AS path."""
        if not self.as_path:
            return "Unknown"
        return " -> ".join([f"AS{asn}" for asn in self.as_path])


class BGPRouteTable(HyperglassModel):
    """Post-parsed BGP route table."""

    vrf: str
    count: int = 0
    routes: t.List[BGPRoute]
    winning_weight: WinningWeight
    asn_organizations: t.Dict[str, t.Dict[str, str]] = {}  # ASN -> {name, country}

    @model_validator(mode="wrap")
    @classmethod
    def validate_rpki_batch(cls, data: t.Any, handler: t.Callable[[t.Any], t.Any]) -> t.Any:
        """Validate external RPKI state for all routes in one batch.

        One table triggers one batch: (prefix, origin ASN) pairs are
        deduplicated and uncached pairs are looked up concurrently.
        """
        if isinstance(data, BGPRouteTable):
            # Assignment re-validation; routes are already resolved.
            return handler(data)

        with defer_rpki():
            table = handler(data)
            structured = use_state("params").structured
            if structured.rpki.mode == "external":
                targets = [_rpki_target(r.prefix, r.as_path, r.rpki_state) for r in table.routes]
                states = rpki_states(
                    (target for target in targets if not isinstance(target, int)),
                    backend=structured.rpki.backend,
                    rpki_server_url=structured.rpki.rpki_server_url,
                )
                for route, target in zip(table.routes, targets):
                    if isinstance(target, int):
                        route.rpki_state = target
                    else:
                        route.rpki_state = states[(str(target[0]), str(target[1]))]
        return table

    def __init__(self, **kwargs):
        """Sort routes by prefix after validation."""
        super().__init__(**kwargs)
        self.routes = sorted(self.routes, key=lambda r: r.prefix)

    def __add__(self: "BGPRouteTable", other: "BGPRouteTable") -> "BGPRouteTable":
        """Merge another BGP table instance with this instance."""
        if isinstance(other, BGPRouteTable):
            self.routes = sorted([*self.routes, *other.routes], key=lambda r: r.prefix)
            self.count = len(self.routes)
        return self

    async def enrich_with_ip_enrichment(self):
        """Enrich BGP routes with next-hop information from IP enrichment."""
        from hyperglass.external.ip_enrichment import network_info

        # Extract unique next-hop IPs that need enrichment
        next_hops_to_lookup = set()
        for route in self.routes:
            if route.next_hop and not route.next_hop_asn:  # Only lookup if not already enriched
                next_hops_to_lookup.add(route.next_hop)

        if not next_hops_to_lookup:
            return

        # Bulk lookup next-hop information
        network_data = await network_info(*list(next_hops_to_lookup))

        # Enrich routes with the retrieved data
        for route in self.routes:
            if route.next_hop in network_data:
                data: TargetDetail = network_data[route.next_hop]
                # Handle ASN formatting
                asn_raw = data.get("asn")
                if asn_raw and asn_raw != "None":
                    route.next_hop_asn = f"AS{asn_raw}"
                else:
                    route.next_hop_asn = None

                route.next_hop_org = data.get("org") if data.get("org") != "None" else None
                route.next_hop_country = (
                    data.get("country") if data.get("country") != "None" else None
                )

    async def enrich_as_path_organizations(self):
        """Enrich AS path ASNs with organization names using bulk lookup."""
        from hyperglass.external.ip_enrichment import lookup_asns_bulk
        from hyperglass.log import log

        _log = log.bind(source="bgp_asn_enrichment")

        # Collect all unique ASNs from AS paths
        all_asns = set()
        for route in self.routes:
            all_asns.update(route.as_path)

        if not all_asns:
            _log.debug("No AS paths found to enrich")
            return

        # Convert to strings and bulk lookup
        asn_strings = [str(asn) for asn in all_asns]

        try:
            asn_data = await lookup_asns_bulk(asn_strings)
            # Store the ASN organization mapping for use by frontend
            self.asn_organizations = asn_data
        except Exception as e:
            _log.error(f"Failed to lookup ASN organizations: {e}")
            self.asn_organizations = {}
