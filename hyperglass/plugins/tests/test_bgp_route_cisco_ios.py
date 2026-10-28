"""Parse Cisco IOS and IOS XE `show bgp` text output (#83)."""

# Standard Library
from pathlib import Path

# Third Party
import pytest

# Project
from hyperglass.exceptions.private import ParsingError, InputValidationError
from hyperglass.defaults.directives.cisco_ios import CiscoIOS_BGPRoute, CiscoIOS_BGPRouteTable
from hyperglass.plugins._builtin.bgp_route_cisco_ios import parse_cisco_ios

FIXTURES = Path(__file__).parent / "fixtures" / "cisco-ios-live"
PREFIXES = {4: "1.0.0.0/24", 6: "2606:4700:4700::/48"}
NEXT_HOPS = {4: "10.250.9.0", 6: "FD00:250:9::"}
HEADER = """BGP table version is 1, local router ID is 10.0.0.1
Status codes: s suppressed, d damped, h history, * valid, > best, i - internal,
Origin codes: i - IGP, e - EGP, ? - incomplete
RPKI validation codes: V valid, I invalid, N Not found

     Network          Next Hop            Metric LocPrf Weight Path
"""


def _parse(name):
    return parse_cisco_ios([(FIXTURES / name).read_text()])


@pytest.mark.parametrize("family", (4, 6))
def test_route_detail(family):
    table = _parse(f"route{family}.txt")
    assert table.count == 1
    route = table.routes[0]
    assert route.prefix == PREFIXES[family]
    assert route.active is True
    assert route.as_path == [65000, 64999, 13335]
    assert route.source_as == 13335
    assert route.next_hop == NEXT_HOPS[family]
    assert route.peer_rid == NEXT_HOPS[family]
    assert route.source_rid == "10.250.0.1"
    assert route.local_preference == 100
    assert route.communities == ["65000:777", "65000:777:1"]
    assert route.age > 0
    assert table.winning_weight == "high"


def test_route_detail_aggregator():
    """The aggregator note after the AS path is not part of the path."""
    route = _parse("route_aggregated4.txt").routes[0]
    assert route.prefix == "1.1.1.0/24"
    assert route.as_path == [65000, 327960, 13335]
    assert route.communities == ["13335:10045"]


@pytest.mark.parametrize("family", (4, 6))
@pytest.mark.parametrize("kind", ("aspath", "community"))
def test_summary_table(kind, family):
    """IPv6 rows wrap the next hop onto a second line. The table has no communities."""
    table = _parse(f"{kind}{family}.txt")
    assert [route.prefix for route in table.routes] == [PREFIXES[family]]
    route = table.routes[0]
    assert route.active is True
    assert route.as_path == [65000, 64999, 13335]
    assert route.next_hop == NEXT_HOPS[family]
    assert route.weight == 0
    assert route.communities == []


def test_summary_table_bulk():
    table = _parse("community_bulk4.txt")
    assert table.count == 35
    assert all(route.as_path[-1] == 13335 for route in table.routes)
    assert all(route.next_hop == "10.250.9.0" for route in table.routes)
    assert table.routes[0].prefix == "104.22.109.0/24"


def test_summary_table_columns():
    """Multiple paths, metrics, internal paths, classful networks and RPKI codes."""
    output = HEADER + "".join(
        f"{status:<6}{network:<17}{next_hop:<20}{metric:>6}{locprf:>7}{weight:>7} {path}\n"
        for status, network, next_hop, metric, locprf, weight, path in (
            ("V*>", "10.0.0.0", "192.0.2.1", "5", "200", "0", "65001 {65002,65003} i"),
            ("N*>i", "198.51.100.0/24", "192.0.2.2", "", "150", "0", "65004 ?"),
            (" *", "", "192.0.2.3", "", "", "100", "65005 e"),
        )
    )
    routes = parse_cisco_ios([output]).routes
    assert [r.prefix for r in routes] == ["10.0.0.0/8", "198.51.100.0/24", "198.51.100.0/24"]
    assert (routes[0].med, routes[0].local_preference, routes[0].weight) == (5, 200, 0)
    assert routes[0].as_path == [65001, 65002, 65003]
    assert routes[0].rpki_state == 1
    assert (routes[1].med, routes[1].local_preference, routes[1].rpki_state) == (0, 150, 2)
    assert routes[2].active is False
    assert (routes[2].next_hop, routes[2].weight, routes[2].as_path) == ("192.0.2.3", 100, [65005])


def test_not_in_table():
    assert parse_cisco_ios(["% Network not in table"]) is None


def test_command_error():
    with pytest.raises(ParsingError):
        parse_cisco_ios(["                ^\n% Invalid input detected at '^' marker."])


@pytest.mark.parametrize("directive", (CiscoIOS_BGPRoute, CiscoIOS_BGPRouteTable))
def test_ipv6_route_needs_prefix(directive):
    """IOS has no longest-match BGP lookup for an IPv6 address (#84)."""
    rule = directive.rules[1]
    assert rule.validate_target("2606:4700::/32", multiple=False) is True
    with pytest.raises(InputValidationError):
        rule.validate_target("2606:4700:4700::1", multiple=False)
    assert directive.rules[0].validate_target("1.0.0.1", multiple=False) is True
