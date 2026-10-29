"""Parse Extreme Networks EXOS `show bgp routes detail` text output."""

# Standard Library
import re
import typing as t

# Project
from hyperglass.log import log
from hyperglass.util import parse_as_path
from hyperglass.models.data import BGPRouteTable

ROUTE = re.compile(r"^Route: (?P<prefix>\S+), Peer (?P<peer>[^,\s]+)(?P<flags>.*)$")
ATTRIBUTES = re.compile(
    r"^Origin \w+, Next-Hop (?P<next_hop>\S+), LPref (?P<lpref>\d+), MED (?P<med>\d+)"
)
WEIGHT = re.compile(r"^Weight (?P<weight>\d+)")


def _new_route(prefix: str, peer: str, flags: str) -> t.Dict[str, t.Any]:
    return {
        "prefix": prefix,
        # `Active` marks the path installed in the route table.
        "active": "Active" in flags.split(", "),
        # EXOS prints no route age, originator or validation state in this view.
        "age": 0,
        "weight": 0,
        "med": 0,
        "local_preference": 100,
        "as_path": [],
        "communities": [],
        "next_hop": "",
        "source_as": 0,
        "source_rid": "",
        "peer_rid": peer,
        "rpki_state": 3,
    }


def parse_extreme_exos_routes(output: str) -> t.List[t.Dict[str, t.Any]]:
    """Convert one EXOS `show bgp routes detail` response to standard route fields."""
    routes = []
    route = None
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("%"):
            raise ValueError(f"EXOS command error: {line}")
        match = ROUTE.match(line)
        if match:
            route = _new_route(match.group("prefix"), match.group("peer"), match.group("flags"))
            routes.append(route)
            continue
        if route is None:
            continue
        match = ATTRIBUTES.match(line)
        if match:
            route["next_hop"] = match.group("next_hop")
            route["local_preference"] = int(match.group("lpref"))
            route["med"] = int(match.group("med"))
            continue
        match = WEIGHT.match(line)
        if match:
            route["weight"] = int(match.group("weight"))
        elif line.startswith("As-PATH:"):
            route["as_path"] = parse_as_path(line.split(":", 1)[1])
            route["source_as"] = route["as_path"][-1] if route["as_path"] else 0
        elif line.startswith("Community:"):
            route["communities"] = line.split(":", 1)[1].split()
        elif line.startswith("BGP Route Statistics"):
            route = None
    return routes


def extreme_exos_bgp_table(routes: t.List[t.Dict[str, t.Any]]) -> BGPRouteTable:
    """Combine parsed EXOS routes into one standard BGP table."""
    serialized = BGPRouteTable(
        vrf="default",
        count=len(routes),
        routes=routes,
        winning_weight="high",
    )

    log.bind(platform="extreme_exos", response=repr(serialized)).debug("Serialized response")
    return serialized
