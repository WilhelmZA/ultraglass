"""Parse BIRD `show route all` text output."""

# Standard Library
import re
import typing as t

# Project
from hyperglass.log import log
from hyperglass.util import parse_asn, parse_as_path
from hyperglass.models.data import BGPRouteTable

ROUTE_HEADER = re.compile(
    r"^(?P<prefix>\S+)?\s+(?P<type>unicast|blackhole|unreachable|prohibit)\s+"
    r"\[(?P<proto>\S+)\s+[^\]]*\]\s+(?P<best>\*)?\s*\((?P<pref>\d+)\)"
)
COMMUNITY = re.compile(r"\((\d+),\s*(\d+)\)")
LARGE_COMMUNITY = re.compile(r"\((\d+),\s*(\d+),\s*(\d+)\)")
AGGREGATOR = re.compile(r"^(?P<rid>\S+)\s+AS(?P<asn>\S+)$")


def _new_route(prefix: str, match: t.Match) -> t.Dict[str, t.Any]:
    return {
        "prefix": prefix,
        "active": match.group("best") is not None,
        # BIRD prints the last change as a configurable timestamp, not an age.
        "age": 0,
        "weight": int(match.group("pref")),
        "med": 0,
        "local_preference": 100,
        "as_path": [],
        "communities": [],
        "next_hop": "",
        "source_as": 0,
        "source_rid": "",
        "peer_rid": match.group("proto"),
        # BIRD does not print an origin validation state.
        "rpki_state": 3,
    }


def _apply_attribute(route: t.Dict[str, t.Any], key: str, value: str) -> None:
    if key == "BGP.as_path":
        route["as_path"] = parse_as_path(value)
    elif key == "BGP.next_hop":
        route["next_hop"] = value.split()[0] if value else ""
    elif key == "BGP.med":
        route["med"] = int(value)
    elif key == "BGP.local_pref":
        route["local_preference"] = int(value)
    elif key == "BGP.community":
        route["communities"].extend(f"{a}:{b}" for a, b in COMMUNITY.findall(value))
    elif key == "BGP.large_community":
        route["communities"].extend(f"{a}:{b}:{c}" for a, b, c in LARGE_COMMUNITY.findall(value))
    elif key == "BGP.aggregator":
        match = AGGREGATOR.match(value)
        if match:
            route["source_rid"] = match.group("rid")
            route["source_as"] = parse_asn(match.group("asn")) or 0


def parse_bird_routes(output: str) -> t.List[t.Dict[str, t.Any]]:
    """Convert `show route all` text to standard route fields."""
    routes = []
    prefix = ""
    route = None
    for line in output.splitlines():
        match = ROUTE_HEADER.match(line)
        if match:
            prefix = match.group("prefix") or prefix
            route = _new_route(prefix, match)
            routes.append(route)
        elif route is not None and line.startswith("\t"):
            key, sep, value = line.strip().partition(":")
            if sep:
                _apply_attribute(route, key, value.strip())
            elif key.startswith("via ") and not route["next_hop"]:
                route["next_hop"] = key.split()[1]
    return routes


def bird_bgp_table(routes: t.List[t.Dict[str, t.Any]]) -> BGPRouteTable:
    """Combine parsed BIRD routes into one standard BGP table."""
    serialized = BGPRouteTable(
        vrf="default",
        count=len(routes),
        routes=routes,
        winning_weight="high",
    )

    log.bind(platform="bird", response=repr(serialized)).debug("Serialized response")
    return serialized
