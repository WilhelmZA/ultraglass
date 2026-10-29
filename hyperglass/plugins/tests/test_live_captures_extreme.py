"""Captured Extreme EXOS lab output (#73)."""

# Standard Library
from pathlib import Path

# Third Party
import pytest

# Project
from hyperglass.exceptions.private import ParsingError
from hyperglass.execution.drivers._common import command_error
from hyperglass.plugins._builtin.trace_route_standard import parse_standard_traceroute
from hyperglass.plugins._builtin.bgp_route_extreme_exos import parse_extreme_exos

EXOS = Path(__file__).parent / "fixtures" / "extreme-exos-live"
TARGETS = {4: "1.1.1.1", 6: "2606:4700::1111"}


def _exos(name):
    return (EXOS / f"{name}.txt").read_text()


def test_exos_route_best_and_alternate_path():
    table = parse_extreme_exos([_exos("route4")])
    assert table.count == 2
    best, alternate = table.routes
    assert best.prefix == alternate.prefix == "1.1.1.0/24"
    assert (best.active, alternate.active) == (True, False)
    assert best.as_path == [65000, 13335]
    assert alternate.as_path == [65001, 6939, 13335]
    assert (best.source_as, alternate.source_as) == (13335, 13335)
    assert (best.next_hop, alternate.next_hop) == ("10.251.2.0", "10.252.2.0")
    assert (best.peer_rid, alternate.peer_rid) == ("10.251.2.0", "10.252.2.0")
    assert (best.med, alternate.med) == (0, 10)
    assert best.local_preference == 100
    assert best.weight == 1
    assert best.communities == ["37195:302"]
    assert alternate.communities == ["6939:1000"]


def test_exos_route_ipv6():
    table = parse_extreme_exos([_exos("route6")])
    assert [r.prefix for r in table.routes] == ["2606:4700::/44"]
    assert table.routes[0].next_hop == "fd00:251:2::"
    assert table.routes[0].active is True


def test_exos_route_not_found():
    assert parse_extreme_exos([_exos("route4_empty")]) is None


@pytest.mark.parametrize("kind", ("aspath", "community"))
def test_exos_pattern_queries_combine_families(kind):
    table = parse_extreme_exos([_exos(f"{kind}4"), _exos(f"{kind}6")])
    routes = {(r.prefix, r.peer_rid): r for r in table.routes}
    assert sorted(routes) == [
        ("2001:4860::/32", "fd00:251:2::"),
        ("8.8.8.0/24", "10.251.2.0"),
        ("8.8.8.0/24", "10.252.2.0"),
    ]
    best = routes["8.8.8.0/24", "10.251.2.0"]
    assert best.active is True
    assert routes["8.8.8.0/24", "10.252.2.0"].active is False
    assert best.communities == ["15169:1", "65000:100"]
    assert best.med == 50
    assert all(r.source_as == 15169 for r in table.routes)


def test_exos_command_error():
    assert command_error(_exos("bad"))
    with pytest.raises(ParsingError):
        parse_extreme_exos([_exos("bad")])


@pytest.mark.parametrize("family", (4, 6))
def test_exos_trace(family):
    text = _exos(f"trace{family}")
    result = parse_standard_traceroute(text, TARGETS[family], "exos")
    assert len(result.hops) == 1
    hop = result.hops[0]
    assert hop.ip_address == TARGETS[family]
    assert (hop.rtt1, hop.rtt2, hop.rtt3) == (0.0, 0.0, 0.0)
    assert hop.loss_pct == 0


@pytest.mark.parametrize("family", (4, 6))
def test_exos_ping_is_not_an_error(family):
    assert not command_error(_exos(f"ping{family}"))
