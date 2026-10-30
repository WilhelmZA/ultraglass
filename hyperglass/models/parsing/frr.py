"""Data Models for Parsing FRRouting JSON Response."""

# Standard Library
import typing as t
from datetime import UTC, datetime

# Third Party
from pydantic import ConfigDict, model_validator

# Project
from hyperglass.log import log
from hyperglass.util import parse_asn, parse_as_path
from hyperglass.models.data import BGPRouteTable

# Local
from ..main import HyperglassModel

FRRPeerType = t.Literal["internal", "external", "confed-internal", "confed-external"]


def _alias_generator(field):
    components = field.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


class _FRRBase(HyperglassModel):
    model_config = ConfigDict(alias_generator=_alias_generator, extra="ignore")


class FRRNextHop(_FRRBase):
    """FRR Next Hop Model."""

    ip: str
    afi: str
    # Multipath and inaccessible next hops can omit these fields.
    metric: int = 0
    accessible: bool = False
    used: bool = False


class FRRPeer(_FRRBase):
    """FRR Peer Model."""

    peer_id: str
    router_id: str
    # Locally sourced paths have no peer type.
    type: t.Optional[FRRPeerType] = None


class FRRPath(_FRRBase):
    """FRR Path Model."""

    aspath: t.List[int]
    aggregator_as: int = 0
    aggregator_id: str = ""
    loc_prf: int = 100  # 100 is the default value for local preference
    metric: int = 0
    med: int = 0
    weight: int = 0
    valid: bool
    # Summary output (AS path and community queries) has no update time.
    last_update: t.Optional[int] = None
    bestpath: bool
    community: t.List[str]
    nexthops: t.List[FRRNextHop]
    peer: FRRPeer

    @model_validator(mode="before")
    def validate_path(cls, values):
        """Extract meaningful data from FRR detail or summary responses."""
        new = values.copy()
        if "aspath" in values:
            # Local prefixes have an empty segment list. Confederation segments are
            # internal to the confederation and are not part of the displayed path.
            segments = values["aspath"].get("segments", [])
            new["aspath"] = parse_as_path(
                [
                    asn
                    for segment in segments
                    if not segment.get("type", "").startswith("as-confed")
                    for asn in segment.get("list", [])
                ]
            )
        else:
            # Summary output carries the AS path as a string.
            new["aspath"] = parse_as_path(values.get("path", ""))
        if "aggregatorAs" in values:
            new["aggregatorAs"] = parse_asn(values["aggregatorAs"]) or 0
        community = values.get("community", {"list": []})
        large_community = values.get("largeCommunity", {"list": []})
        new["community"] = [*community["list"], *large_community["list"]]
        if "lastUpdate" in values:
            new["lastUpdate"] = values["lastUpdate"]["epoch"]
        bestpath = values.get("bestpath", {})
        if isinstance(bestpath, dict):
            bestpath = bestpath.get("overall", False)
        new["bestpath"] = bestpath
        if "peer" not in values:
            peer_id = values.get("peerId", "")
            new["peer"] = {"peerId": peer_id, "routerId": peer_id}
        return new


class FRRBGPTable(_FRRBase):
    """FRR Route Model."""

    prefix: str
    paths: t.List[FRRPath] = []

    def bgp_table(self) -> BGPRouteTable:
        """Convert the FRR-specific fields to standard parsed data model."""
        return frr_bgp_table([self])

    def routes(self) -> t.List[t.Dict[str, t.Any]]:
        """Convert each FRR path to standard route fields."""
        routes = []
        for route in self.paths:
            now = datetime.now(UTC).timestamp()
            age = 0 if route.last_update is None else int(now - route.last_update)
            routes.append(
                {
                    "prefix": self.prefix,
                    "active": route.bestpath,
                    "age": age,
                    "weight": route.weight,
                    "med": route.med,
                    "local_preference": route.loc_prf,
                    "as_path": route.aspath,
                    "communities": route.community,
                    "next_hop": route.nexthops[0].ip,
                    "source_as": route.aggregator_as,
                    "source_rid": route.aggregator_id,
                    "peer_rid": route.peer.peer_id,
                    # TODO: somehow, get the actual RPKI state
                    # This depends on whether or not the RPKI module is enabled in FRR
                    "rpki_state": 3,
                }
            )
        return routes


def frr_bgp_table(tables: t.Sequence[FRRBGPTable], vrf: str = "default") -> BGPRouteTable:
    """Combine FRR prefixes into one standard BGP table."""

    routes = [route for table in tables for route in table.routes()]

    serialized = BGPRouteTable(
        vrf=vrf,
        count=len(routes),
        routes=routes,
        winning_weight="high",
    )

    log.bind(platform="frr", response=repr(serialized)).debug("Serialized response")
    return serialized
