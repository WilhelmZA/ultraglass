"""Parser for Huawei VRP."""

# Standard Library
import re
import typing as t
from ipaddress import ip_address, ip_network

# Third Party
from pydantic import ConfigDict, field_validator, model_validator

# Project
from hyperglass.log import log
from hyperglass.util import parse_asn, parse_as_path
from hyperglass.models.data.bgp_route import BGPRouteTable

# Local
from ..main import HyperglassModel

RPKI_STATE_MAP = {
    "invalid": 0,
    "valid": 1,
    "unknown": 2,
    "unverified": 3,
}


def remove_prefix(text: str, prefix: str) -> str:
    """Remove prefix from text if it exists."""
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text


class HuaweiBase(HyperglassModel, extra="ignore"):
    """Base Huawei model."""

    def __init__(self, **kwargs: t.Any) -> None:
        """Initialize Huawei model."""
        super().__init__(**kwargs)


class HuaweiPaths(HuaweiBase):
    """BGP paths information."""

    available: int = 0
    best: int = 0
    select: int = 0
    best_external: int = 0
    add_path: int = 0


class HuaweiRouteEntry(HuaweiBase):
    """Parse Huawei route entry data."""

    model_config = ConfigDict(validate_assignment=False)

    prefix: str
    from_addr: str = ""
    from_router_id: str = ""
    duration: int = 0
    direct_out_interface: str = ""
    original_next_hop: str = ""
    relay_ip_next_hop: str = ""
    relay_ip_out_interface: str = ""
    qos: str = ""
    communities: t.List[str] = []
    large_communities: t.List[str] = []
    ext_communities: t.List[str] = []
    as_path: t.List[int] = []
    origin: str = ""
    metric: int = 0  # MED
    local_preference: int = 100
    preference_value: int = 0
    is_valid: bool = False
    is_external: bool = False
    is_backup: bool = False
    is_best: bool = False
    is_selected: bool = False
    preference: int = 0

    @property
    def next_hop(self) -> str:
        """Get next hop (original or relay IP)."""
        return self.original_next_hop or self.relay_ip_next_hop

    @property
    def age(self) -> str:
        """Get age as string."""
        return str(self.duration)

    @property
    def weight(self) -> int:
        """Get weight from the VRP preferred value (`pref-val`, `PrefVal`).

        `preference` holds the route preference (`pre`), which is not the BGP weight.
        """
        return self.preference_value

    @property
    def med(self) -> int:
        """Get MED (metric)."""
        return self.metric

    @property
    def active(self) -> bool:
        """Check if route is active (best or selected)."""
        return self.is_best or self.is_selected

    @property
    def all_communities(self) -> t.List[str]:
        """Get standard and large communities.

        Extended communities (route targets such as `RT 64501 : 1`) are not
        standard communities and stay out of the community list.
        """
        return self.communities + self.large_communities

    @property
    def source_as(self) -> int:
        """Get source AS from AS path (first ASN in the path)."""
        return self.as_path[0] if self.as_path else 0

    @property
    def source_rid(self) -> str:
        """Get the router ID printed in parentheses after `From:`."""
        return self.from_router_id

    @property
    def peer_rid(self) -> str:
        """Get peer router ID."""
        return self.from_addr


def _extract_paths(line: str) -> HuaweiPaths:
    """Extract paths information from line like 'Paths: 3 available, 1 best, 1 select, 0 best-external, 0 add-path'."""
    paths_data = {
        "available": 0,
        "best": 0,
        "select": 0,
        "best_external": 0,
        "add_path": 0,
    }

    try:
        values = remove_prefix(line.strip(), "Paths:").strip().split(",")
        for value in values:
            parts = value.strip().split(" ")
            if len(parts) >= 2:
                count = int(parts[0])
                name = parts[1].replace("-", "_")  # Convert best-external to best_external
                if name in paths_data:
                    paths_data[name] = count
    except (ValueError, IndexError):
        log.warning(f"Failed to parse paths line: {line}")

    return HuaweiPaths(**paths_data)


def _extract_route_entries(lines: t.List[str]) -> t.List[HuaweiRouteEntry]:
    """Extract route entries from lines."""
    routes = []

    # Split lines into route blocks using empty lines as separators
    size = len(lines)
    idx_list = [idx + 1 for idx, val in enumerate(lines) if val.strip() == ""]
    entries = (
        [
            lines[i:j]
            for i, j in zip([0] + idx_list, idx_list + ([size] if idx_list[-1] != size else []))
        ]
        if idx_list
        else [lines]
    )

    for route_entry in entries:
        if not route_entry:
            continue

        # Initialize route data
        route_data = {
            "prefix": "",
            "from_addr": "",
            "from_router_id": "",
            "duration": 0,
            "direct_out_interface": "",
            "original_next_hop": "",
            "relay_ip_next_hop": "",
            "relay_ip_out_interface": "",
            "qos": "",
            "communities": [],
            "large_communities": [],
            "ext_communities": [],
            "as_path": [],
            "origin": "",
            "metric": 0,
            "local_preference": 100,
            "preference_value": 0,
            "is_valid": False,
            "is_external": False,
            "is_backup": False,
            "is_best": False,
            "is_selected": False,
            "preference": 0,
        }

        for info in route_entry:
            info = info.strip()
            if not info:
                continue

            if info.startswith("BGP routing table entry information of"):
                route_data["prefix"] = remove_prefix(
                    info, "BGP routing table entry information of "
                ).rstrip(":")
            elif info.startswith("From:"):
                peer = re.match(r"From:\s*(\S+)(?:\s*\(([^)]*)\))?", info)
                route_data["from_addr"] = peer[1] if peer else ""
                route_data["from_router_id"] = (peer[2] or "").strip() if peer else ""
            elif info.startswith("Route Duration:"):
                duration_str = remove_prefix(info, "Route Duration: ")
                try:
                    # Parse format like "84d11h53m07s"
                    d_match = re.search(r"(\d+)d", duration_str)
                    h_match = re.search(r"(\d+)h", duration_str)
                    m_match = re.search(r"(\d+)m", duration_str)
                    s_match = re.search(r"(\d+)s", duration_str)

                    days = int(d_match.group(1)) if d_match else 0
                    hours = int(h_match.group(1)) if h_match else 0
                    minutes = int(m_match.group(1)) if m_match else 0
                    seconds = int(s_match.group(1)) if s_match else 0

                    route_data["duration"] = (
                        days * 24 * 60 * 60 + hours * 60 * 60 + minutes * 60 + seconds
                    )
                except:
                    route_data["duration"] = 0
            elif info.startswith("Direct Out-interface:"):
                route_data["direct_out_interface"] = remove_prefix(info, "Direct Out-interface: ")
            elif info.startswith("Original nexthop:"):
                route_data["original_next_hop"] = remove_prefix(info, "Original nexthop: ")
            elif info.startswith("Relay IP Nexthop:"):
                route_data["relay_ip_next_hop"] = remove_prefix(info, "Relay IP Nexthop: ")
            elif info.startswith("Relay IP Out-Interface:"):
                route_data["relay_ip_out_interface"] = remove_prefix(
                    info, "Relay IP Out-Interface: "
                )
            elif info.startswith("Qos information :"):
                route_data["qos"] = remove_prefix(info, "Qos information : ")
            elif info.startswith("Community:"):
                communities_str = remove_prefix(info, "Community: ")
                if communities_str and communities_str.lower() != "none":
                    communities = [
                        c.strip().replace("<", "").replace(">", "")
                        for c in communities_str.split(", ")
                    ]
                    route_data["communities"] = [c for c in communities if c]
            elif info.startswith("Large-Community:"):
                large_communities_str = remove_prefix(info, "Large-Community: ")
                if large_communities_str and large_communities_str.lower() != "none":
                    large_communities = [
                        c.strip().replace("<", "").replace(">", "")
                        for c in large_communities_str.split(", ")
                    ]
                    route_data["large_communities"] = [c for c in large_communities if c]
            elif info.startswith("Ext-Community:"):
                ext_communities_str = remove_prefix(info, "Ext-Community: ")
                if ext_communities_str and ext_communities_str.lower() != "none":
                    ext_communities = [
                        c.strip().replace("<", "").replace(">", "")
                        for c in ext_communities_str.split(", ")
                    ]
                    route_data["ext_communities"] = [c for c in ext_communities if c]
            elif info.startswith("AS-path"):
                values = info.split(",")
                for v in values:
                    v = v.strip()
                    if v.startswith("AS-path"):
                        as_path_str = remove_prefix(v, "AS-path ")
                        route_data["as_path"] = parse_as_path(as_path_str)
                    elif v.startswith("origin"):
                        route_data["origin"] = remove_prefix(v, "origin ")
                    elif v.startswith("MED"):
                        try:
                            route_data["metric"] = int(remove_prefix(v, "MED "))
                        except ValueError:
                            route_data["metric"] = 0
                    elif v.startswith("localpref"):
                        try:
                            route_data["local_preference"] = int(remove_prefix(v, "localpref "))
                        except ValueError:
                            route_data["local_preference"] = 100
                    elif v.startswith("pref-val"):
                        try:
                            route_data["preference_value"] = int(remove_prefix(v, "pref-val "))
                        except ValueError:
                            route_data["preference_value"] = 0
                    elif v.startswith("pre "):
                        try:
                            route_data["preference"] = int(remove_prefix(v, "pre "))
                        except ValueError:
                            route_data["preference"] = 0
                    elif v.strip() == "valid":
                        route_data["is_valid"] = True
                    elif v.strip() == "external":
                        route_data["is_external"] = True
                    elif v.strip() == "backup":
                        route_data["is_backup"] = True
                    elif v.strip() == "best":
                        route_data["is_best"] = True
                    elif v.strip() == "select":
                        route_data["is_selected"] = True

        # Only add route if we have a valid prefix
        if route_data["prefix"]:
            try:
                route = HuaweiRouteEntry(**route_data)
                routes.append(route)
            except Exception as e:
                log.warning(
                    "Failed to create route entry for prefix {}: {}",
                    route_data.get("prefix", "unknown"),
                    e,
                )
                continue

    return routes


def _brief_route(prefix: str, flags: str, values: dict) -> HuaweiRouteEntry:
    """Map only attributes present in a brief VRP response."""
    path = values.get("Path/Ogn", "").strip()
    # VRP prints 4-byte ASNs in asdot (`5.280`). AS sets cannot be represented
    # losslessly by this model.
    if path and not re.fullmatch(r"(?:\d+(?:\.\d+)?\s+)*(?:\d+(?:\.\d+)?)?\s*[ie?]", path):
        raise ValueError(f"Unsupported Huawei AS path: {path}")
    as_path = [parse_asn(asn) for asn in re.findall(r"\d+(?:\.\d+)?", path)]
    if None in as_path:
        raise ValueError(f"Unsupported Huawei AS path: {path}")
    return HuaweiRouteEntry(
        prefix=str(ip_network(prefix)),
        original_next_hop=str(ip_address(values.get("NextHop", "").strip())),
        metric=int(values.get("MED", "").strip() or 0),
        local_preference=int(values.get("LocPrf", "").strip() or 100),
        preference_value=int(values.get("PrefVal", "").strip() or 0),
        duration=-1,
        as_path=as_path,
        communities=re.findall(r"\d+:\d+(?::\d+)?", values.get("Community", "")),
        is_valid="*" in flags,
        is_best=">" in flags,
    )


def _brief_fields(line: str) -> dict:
    """Read IPv6 field labels without consuming a neighbouring empty value."""
    labels = list(re.finditer(r"(NextHop|LocPrf|MED|PrefVal|Path/Ogn|Community)\s*:", line))
    return {
        match[1]: line[
            match.end() : labels[index + 1].start() if index + 1 < len(labels) else len(line)
        ].strip()
        for index, match in enumerate(labels)
    }


def _extract_brief_routes(lines: t.List[str]) -> t.List[HuaweiRouteEntry]:
    """Read IPv4 columns and IPv6 labelled blocks from captured VRP output."""
    routes = []
    columns = []
    prefix = ""
    block = None
    flags = ""
    for line in lines:
        if "Network" in line and "NextHop" in line and "PrefVal" in line:
            columns = [(match.group(), match.start()) for match in re.finditer(r"\S+", line)]
            continue
        network = re.match(r"^\s*([*>idh sS]*)\s+Network\s*:\s*(\S+)\s+PrefixLen\s*:\s*(\d+)", line)
        if network:
            if block is not None:
                routes.append(_brief_route(prefix, flags, block))
            flags, address, length = network.groups()
            prefix = f"{address}/{length}"
            block = {}
            continue
        if block is not None:
            block.update(_brief_fields(line))
            continue
        if columns and re.match(r"^\s*[*>idh sS]*[*>]", line):
            values = {
                name: line[
                    start : columns[index + 1][1] if index + 1 < len(columns) else None
                ].strip()
                for index, (name, start) in enumerate(columns)
            }
            prefix = values["Network"] or prefix
            if not prefix:
                raise ValueError("Huawei brief route has no prefix")
            routes.append(_brief_route(prefix, line[: columns[0][1]], values))
    if block is not None:
        routes.append(_brief_route(prefix, flags, block))
    count = re.search(r"Total Number of Routes\s*:\s*(\d+)", "\n".join(lines))
    if count and int(count[1]) != len(routes):
        raise ValueError("Incomplete or unsupported Huawei brief routing table")
    return routes


class HuaweiBGPRouteTable(BGPRouteTable):
    """Canonical Huawei BGP Route Table."""

    # No custom __init__ needed; inherit from BGPRouteTable (which should be a Pydantic model)


class HuaweiBGPTable(HuaweiBase):
    """Validation model for Huawei BGP table data."""

    local_router_id: str = ""
    local_as_number: int = 0
    paths: HuaweiPaths = HuaweiPaths()
    routes: t.List[HuaweiRouteEntry] = []

    @classmethod
    def parse_text(cls, text: str) -> "HuaweiBGPTable":
        """Parse Huawei BGP text output."""
        _log = log.bind(parser="HuaweiBGPTable")

        instance = cls()

        lines = text.split("\n")

        # Extract general information
        for line in lines:
            if "BGP local router ID" in line:
                instance.local_router_id = remove_prefix(line, "BGP local router ID : ").strip()
            elif "Local AS number" in line:
                try:
                    instance.local_as_number = int(
                        remove_prefix(line, "Local AS number : ").strip()
                    )
                except ValueError:
                    instance.local_as_number = 0
            elif line.strip().startswith("Paths:"):
                instance.paths = _extract_paths(line)

        # Extract route entries
        instance.routes = _extract_route_entries(lines)
        if not instance.routes:
            instance.routes = _extract_brief_routes(lines)

        _log.debug(f"Parsed {len(instance.routes)} Huawei routes")
        return instance

    def bgp_table(self) -> BGPRouteTable:
        """Convert to standard BGP table format."""
        routes = []

        for route in self.routes:
            route_data = {
                "prefix": route.prefix,
                "active": route.active,
                "age": route.age,
                "weight": route.weight,
                "med": route.med,
                "local_preference": route.local_preference,
                "as_path": route.as_path,
                "communities": route.all_communities,
                "next_hop": route.next_hop,
                "source_as": route.source_as,
                "source_rid": route.source_rid,
                "peer_rid": route.peer_rid,
                # VRP's '*' / 'valid' marks BGP usability, not RPKI validation.
                "rpki_state": RPKI_STATE_MAP["unverified"],
            }
            # BGPRouteTable validates the routes, RPKI included, in one batch.
            routes.append(route_data)

        return HuaweiBGPRouteTable(
            vrf="default",
            count=len(routes),
            routes=routes,
            winning_weight="high",
        )
