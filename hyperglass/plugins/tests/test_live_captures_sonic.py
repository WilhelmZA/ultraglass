"""Captured community SONiC lab output (#76)."""

# Standard Library
from pathlib import Path

# Third Party
import pytest

# Project
from hyperglass.plugins._builtin.bgp_route_frr import parse_frr
from hyperglass.plugins._builtin.trace_route_frr import parse_frr_traceroute

SONIC = Path(__file__).parent / "fixtures" / "sonic-live"
TARGETS = {4: "1.1.1.1", 6: "2606:4700::1111"}


@pytest.mark.parametrize("family,prefix", [(4, "1.1.1.0/24"), (6, "2606:4700::/44")])
def test_sonic_route(family, prefix):
    table = parse_frr([(SONIC / f"route{family}.json").read_text()])
    assert table.count == 1
    route = table.routes[0]
    assert route.prefix == prefix
    assert route.active is True
    assert route.as_path == [65000, 13335]
    assert route.communities == ["37195:302"]


def test_sonic_route_not_found():
    assert parse_frr([(SONIC / "route4_empty.json").read_text()]) is None


@pytest.mark.parametrize("kind", ("aspath", "community"))
def test_sonic_pattern_queries_combine_families(kind):
    table = parse_frr([(SONIC / f"{kind}{family}.json").read_text() for family in (4, 6)])
    assert sorted(route.prefix for route in table.routes) == ["2001:4860::/32", "8.8.8.0/24"]
    assert all(route.as_path == [65000, 3356, 15169] for route in table.routes)


@pytest.mark.parametrize("family", (4, 6))
def test_sonic_trace(family):
    text = (SONIC / f"trace{family}.txt").read_text()
    result = parse_frr_traceroute(text, TARGETS[family], "sonic")
    assert [hop.ip_address for hop in result.hops] == [TARGETS[family]]
