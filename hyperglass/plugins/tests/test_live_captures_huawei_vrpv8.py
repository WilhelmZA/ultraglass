"""Captured Huawei VRPv8 (VRP 8.180) responses for #103."""

from pathlib import Path

import pytest

from hyperglass.state import use_state
from hyperglass.plugins._builtin.bgp_routestr_huawei import parse_huawei
from hyperglass.plugins._builtin.trace_route_huawei import parse_huawei_traceroute

FIXTURES = Path(__file__).parent / "fixtures" / "huawei-vrpv8-live"


def sample(name):
    """Read one complete device response."""
    return (FIXTURES / f"{name}.txt").read_text()


@pytest.fixture(autouse=True)
def router_rpki():
    params = use_state("params")
    params.structured.rpki.mode = "router"
    params.structured.communities.mode = "deny"
    params.structured.communities.items = []


@pytest.mark.parametrize(
    "name,paths",
    [
        ("aspath4", [[65000, 327960, 13335], [65000, 327960, 13335]]),
        ("aspath6", [[65000, 327960, 174, 13335]]),
    ],
)
def test_aspath_tables(name, paths):
    table = parse_huawei((sample(name),))
    assert table.count == len(table.routes) == len(paths)
    assert [route.as_path for route in table.routes] == paths
    assert all(route.active and route.communities == [] for route in table.routes)


def test_community_tables():
    table = parse_huawei((sample("community4"),))
    assert table.count == 38
    assert all(route.communities == ["37195:302"] for route in table.routes)
    assert parse_huawei((sample("community6"),)).count == 0


def test_route_detail():
    (route,) = parse_huawei((sample("route4"),)).routes
    assert route.prefix == "1.1.1.0/24"
    assert route.active
    assert route.as_path == [65000, 327960, 13335]
    assert route.communities == ["13335:10045"]
    assert route.next_hop == "10.250.8.0"
    assert route.peer_rid == "10.250.8.0"
    assert route.source_rid == "10.250.0.1"
    assert route.weight == 0
    assert route.age == 180


def test_vpn_instance_route_detail():
    """Anonymised NE output with two paths and a route-target ext-community."""
    first, second = parse_huawei((sample("route4_vpn_instance"),)).routes
    assert first.prefix == second.prefix == "8.8.8.0/24"

    assert first.active
    assert first.as_path == [64500, 15169]
    assert first.local_preference == 120
    assert first.communities == ["64500:6", "64500:7", "65001:1003"]
    assert first.next_hop == "198.51.100.1"
    assert first.peer_rid == "198.51.100.1"
    assert first.source_rid == "198.51.100.101"

    assert not second.active
    assert second.as_path == [64501, 15169]
    assert second.local_preference == 110
    assert second.communities == ["64501:20508", "65001:1000", "65001:1006"]
    assert second.next_hop == "198.51.100.2"
    assert second.source_rid == "198.51.100.102"


def test_ping_capture_is_complete():
    text = sample("ping4")
    assert text.count("Reply from 1.1.1.1") == 5
    assert "0.00% packet loss" in text


def test_trace_parses_to_hop_table():
    trace = parse_huawei_traceroute(sample("trace4"), "1.1.1.1", "lab-huawei-vrpv8")
    assert [hop.hop_number for hop in trace.hops] == list(range(1, 10))
    assert trace.hops[0].ip_address == "10.250.8.0"
    assert trace.hops[-1].ip_address == "1.1.1.1"
