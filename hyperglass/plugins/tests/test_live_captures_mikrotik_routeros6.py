"""Captured MikroTik RouterOS 6.49 lab output (#117)."""

# Standard Library
import json
from pathlib import Path

# Project
from hyperglass.execution.drivers._common import command_error
from hyperglass.plugins._builtin.bgp_routestr_mikrotik import parse_mikrotik
from hyperglass.plugins._builtin.mikrotik_garbage_output import MikrotikGarbageOutput

ROS6 = Path(__file__).parent / "fixtures" / "mikrotik-routeros6-live"


def _raw(name):
    return json.loads((ROS6 / f"{name}.json").read_text())["raw"]


def _parse(name):
    cleaned = MikrotikGarbageOutput().process(output=tuple(_raw(name)), query=None)
    return parse_mikrotik(cleaned)


def test_routeros6_route_with_med_and_communities():
    table = _parse("route4")
    assert table.count == 1
    route = table.routes[0]
    assert route.prefix == "1.0.0.0/24"
    # RouterOS 6 prints the route index before the flags; `A` marks the active route.
    assert route.active is True
    assert route.as_path == [65000, 64999, 13335]
    assert route.source_as == 13335
    assert route.next_hop == "10.251.8.2"
    assert route.med == 50
    assert route.communities == ["65000:777", "65000:778"]


def test_routeros6_route_ipv6():
    table = _parse("route6")
    assert [r.prefix for r in table.routes] == ["2606:4700::/44"]
    assert table.routes[0].next_hop == "fd00:251:8::2"
    assert table.routes[0].active is True


def test_routeros6_route_not_found():
    assert _parse("route4_empty").count == 0


def test_routeros6_aspath_reads_both_families_from_one_command():
    table = _parse("aspath")
    assert {r.prefix for r in table.routes} == {
        "1.0.0.0/24",
        "1.1.1.0/24",
        "2606:4700::/44",
        "2606:4700:4700::/48",
    }
    assert all(r.active and r.source_as == 13335 for r in table.routes)


def test_routeros6_community_matches_inside_a_list():
    """RouterOS 6 joins a community list with `;`, so 65000:777 is not the last value."""
    table = _parse("community")
    assert {r.prefix: r.communities for r in table.routes} == {
        "1.0.0.0/24": ["65000:777", "65000:778"],
        "2606:4700:4700::/48": ["65000:777"],
    }


def test_routeros7_command_is_a_command_error_on_routeros6():
    assert command_error(tuple(_raw("bad")))
    assert not command_error(tuple(_raw("route4_empty")))
