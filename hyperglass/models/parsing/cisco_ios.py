"""Parse Cisco IOS, IOS XE, IOS-XR and NX-OS `show bgp` text output."""

# Standard Library
import re
import typing as t
from datetime import UTC, datetime
from ipaddress import ip_network

# Project
from hyperglass.log import log
from hyperglass.util import parse_as_path
from hyperglass.models.data import BGPRouteTable

ENTRY = re.compile(r"^BGP routing table entry for (?P<prefix>[^\s,]+)")
NEXT_HOP = re.compile(r"^ {4}(?P<next_hop>\S+).* from (?P<peer>\S+) \((?P<rid>[^)]+)\)")
UPDATED = re.compile(r"Updated on (?P<time>\w{3} +\d+ \d{4} \d\d:\d\d:\d\d) (?P<tz>\S+)")
RPKI_DETAIL = re.compile(
    r"(?:RPKI State|Origin-AS validity:) (?P<state>valid|invalid|not found|not-found)"
)
RPKI_STATES = {"valid": 1, "invalid": 0, "not found": 2, "not-found": 2, "V": 1, "I": 0, "N": 2}
# NX-OS starts each path of a detail entry with its type and prints the AS path below it.
NXOS_PATH = re.compile(r"^ {2}Path type: ")
NXOS_AS_PATH = re.compile(r"^ {2}AS-Path: (?P<path>[^,]*)")
# A summary-table path starts with a status code; footer lines such as `Processed` do not.
STATUS_CODES = "*sdhrSxVIN"
# Status-column offset and status-code RPKI letters per platform. IOS prints a path's
# status one character right of the header. NX-OS uses `I` for an injected path and
# IOS-XR uses `N` for a next-hop discard, so only IOS status codes carry RPKI state.
TABLE_LAYOUT = {
    "cisco_ios": {"shift": 1, "rpki": True},
    "cisco_xr": {"shift": 0, "rpki": False},
    "cisco_nxos": {"shift": 0, "rpki": False},
}
# An empty result is a normal answer; any other `%` line is a command error. IOS-XR
# prints the message with `%%`.
NOT_FOUND = ("% Network not in table", "%% Network not in table")


def _new_route(prefix: str) -> t.Dict[str, t.Any]:
    return {
        "prefix": prefix,
        "active": False,
        "age": 0,
        "weight": 0,
        "med": 0,
        "local_preference": 100,
        "as_path": [],
        "communities": [],
        "next_hop": "",
        "source_as": 0,
        "source_rid": "",
        "peer_rid": "",
        # IOS prints a validation state only when the router validates origins.
        "rpki_state": 3,
    }


def _finish(route: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    route["source_as"] = route["as_path"][-1] if route["as_path"] else 0
    return route


def _classful(network: str) -> str:
    """Add the classful length IOS omits from some IPv4 networks."""
    if "/" in network or ":" in network:
        return network
    first = int(network.split(".")[0])
    length = 8 if first < 128 else 16 if first < 192 else 24
    return str(ip_network(f"{network}/{length}", strict=False))


def _age(match: t.Match) -> int:
    # Only a UTC timestamp converts to an age without the device's time zone rules.
    if match.group("tz") != "UTC":
        return 0
    updated = datetime.strptime(match.group("time"), "%b %d %Y %H:%M:%S").replace(tzinfo=UTC)
    return max(int((datetime.now(UTC) - updated).total_seconds()), 0)


def _apply_attributes(route: t.Dict[str, t.Any], line: str) -> None:
    for field in (part.strip() for part in line.split(",")):
        key, _, value = field.partition(" ")
        if key == "metric":
            route["med"] = int(value)
        elif key == "localpref":
            route["local_preference"] = int(value)
        elif key == "weight":
            route["weight"] = int(value)
        elif key == "MED" and value.isdigit():
            route["med"] = int(value)
        elif key == "best":
            route["active"] = True


def _apply_path_line(route: t.Dict[str, t.Any], line: str) -> None:
    stripped = line.strip()
    next_hop = NEXT_HOP.match(line)
    if next_hop:
        route["next_hop"] = next_hop.group("next_hop")
        route["peer_rid"] = next_hop.group("peer")
        route["source_rid"] = next_hop.group("rid")
    elif stripped.startswith("Origin "):
        _apply_attributes(route, stripped)
    elif stripped.startswith("Community: "):
        route["communities"].extend(stripped.removeprefix("Community: ").split())
    elif stripped.startswith("Large Community: "):
        route["communities"].extend(stripped.removeprefix("Large Community: ").split())
    if match := UPDATED.search(stripped):
        route["age"] = _age(match)
    if match := RPKI_DETAIL.search(stripped):
        route["rpki_state"] = RPKI_STATES[match.group("state")]


def parse_detail(output: str) -> t.List[t.Dict[str, t.Any]]:
    """Convert `show bgp <afi> unicast <prefix>` path detail to standard route fields."""
    routes = []
    prefix = ""
    route = None
    for line in output.splitlines():
        entry = ENTRY.match(line)
        if entry:
            prefix = _classful(entry.group("prefix"))
            route = None
            continue
        if not prefix:
            continue
        # Each path starts with its AS path, or `Local`, indented by two spaces.
        if re.match(r"^ {2}(Local|[\d({\[])", line):
            route = _new_route(prefix)
            routes.append(route)
            route["as_path"] = parse_as_path(line.split(", ")[0])
            continue
        if NXOS_PATH.match(line):
            route = _new_route(prefix)
            routes.append(route)
            route["active"] = "is best path" in line
            continue
        if route is not None and (match := NXOS_AS_PATH.match(line)):
            route["as_path"] = parse_as_path(match.group("path"))
            continue
        if route is not None:
            _apply_path_line(route, line)
    return [_finish(route) for route in routes]


def parse_table(output: str, platform: str = "cisco_ios") -> t.List[t.Dict[str, t.Any]]:
    """Convert the `show bgp <afi> unicast` summary table to standard route fields.

    The summary table carries no communities. IOS moves a long network onto its own
    line and continues the path on the next line, which aligns with the header. A line
    that starts with a status code sits one character right of the header on IOS.
    """
    layout = TABLE_LAYOUT[platform]
    routes = []
    columns = None
    prefix = ""
    route = None
    for line in output.splitlines():
        if line.lstrip().startswith("Network") and "Next Hop" in line:
            columns = {
                "network": line.index("Network"),
                "next_hop": line.index("Next Hop"),
                "metric": line.index("Metric") + len("Metric"),
                "locprf": line.index("LocPrf") + len("LocPrf"),
                "weight": line.index("Weight") + len("Weight"),
                "path": line.index("Path"),
            }
            continue
        if columns is None or not line.strip():
            continue
        status = line[: columns["network"] + layout["shift"]]
        if status.strip() and status.strip()[0] not in STATUS_CODES:
            continue
        shift = layout["shift"] if status.strip() else 0
        col = {name: index + shift for name, index in columns.items()}
        if status.strip():
            # A status code starts a path. Further paths of a prefix leave the network blank.
            network = line[col["network"] :].split()
            has_network = bool(network) and not line[col["network"]].isspace()
            if has_network:
                prefix = _classful(network[0])
            route = _new_route(prefix)
            route["active"] = ">" in status
            if layout["rpki"]:
                route["rpki_state"] = next((RPKI_STATES[c] for c in status if c in "VIN"), 3)
            routes.append(route)
            if has_network and col["network"] + len(network[0]) >= col["next_hop"]:
                # A long network takes the whole line.
                continue
        if route is None:
            continue
        metric_start = col["next_hop"]
        if len(line) > metric_start and not line[metric_start].isspace():
            route["next_hop"] = line[metric_start:].split()[0]
            metric_start += len(route["next_hop"])
        if len(line) <= col["path"]:
            continue
        metric = line[metric_start : col["metric"]].strip()
        locprf = line[col["metric"] : col["locprf"]].strip()
        weight = line[col["locprf"] : col["weight"]].strip()
        route["med"] = int(metric) if metric else 0
        route["local_preference"] = int(locprf) if locprf else 100
        route["weight"] = int(weight) if weight else 0
        # The last path token is the origin code.
        route["as_path"] = parse_as_path(line[col["path"] :].rsplit(maxsplit=1)[0])
    return [_finish(route) for route in routes]


def parse_cisco_ios_routes(output: str, platform: str = "cisco_ios") -> t.List[t.Dict[str, t.Any]]:
    """Convert one Cisco `show bgp` response, in either form, to standard route fields."""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("%") and stripped not in NOT_FOUND:
            raise ValueError(f"Cisco command error: {stripped}")
    if "BGP routing table entry for" in output:
        return parse_detail(output)
    return parse_table(output, platform)


def cisco_ios_bgp_table(
    routes: t.List[t.Dict[str, t.Any]], platform: str = "cisco_ios"
) -> BGPRouteTable:
    """Combine parsed Cisco routes into one standard BGP table."""
    serialized = BGPRouteTable(
        vrf="default",
        count=len(routes),
        routes=routes,
        winning_weight="high",
    )

    log.bind(platform=platform, response=repr(serialized)).debug("Serialized response")
    return serialized
