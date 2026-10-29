"""Captured Cisco IOS-XR, NX-OS and IOSv lab output (#99, #100)."""

# Standard Library
from pathlib import Path

# Third Party
import pytest

# Project
from hyperglass.exceptions.private import ParsingError
from hyperglass.execution.drivers._common import command_error
from hyperglass.plugins._builtin.bgp_route_cisco_ios import parse_cisco_ios
from hyperglass.plugins._builtin.trace_route_standard import parse_standard_traceroute

FIXTURES = Path(__file__).parent / "fixtures"
TARGETS = {4: "1.1.1.1", 6: "2606:4700::1111"}
PREFIXES = {4: "1.1.1.0/24", 6: "2606:4700::/44"}


@pytest.mark.parametrize(
    ("platform", "family", "rtts"),
    [
        ("cisco-xr-live", 4, (0.0, 0.0, None)),
        ("cisco-xr-live", 6, (1.0, 1.0, None)),
        ("cisco-nxos-live", 4, (1.854, 1.663, 1.956)),
        ("cisco-nxos-live", 6, (3.242, 2.647, 2.207)),
        ("cisco-iosv-live", 4, (1.0, 0.0, None)),
        ("cisco-iosv-live", 6, (1.0, 1.0, 1.0)),
    ],
)
def test_captured_trace(platform, family, rtts):
    text = (FIXTURES / platform / f"trace{family}.txt").read_text()
    result = parse_standard_traceroute(text, TARGETS[family], platform)
    assert len(result.hops) == 1
    hop = result.hops[0]
    assert hop.ip_address == TARGETS[family]
    assert (hop.rtt1, hop.rtt2, hop.rtt3) == rtts
    assert hop.sent_count == sum(rtt is not None for rtt in rtts)
    assert hop.loss_pct == 0
    assert result.raw_output == text


@pytest.mark.parametrize("family", (4, 6))
def test_iosv_route_detail(family):
    table = parse_cisco_ios([(FIXTURES / "cisco-iosv-live" / f"route{family}.txt").read_text()])
    assert table.count == 1
    route = table.routes[0]
    assert route.prefix == PREFIXES[family]
    assert route.active is True
    assert route.as_path == [65000, 13335]
    assert route.source_as == 13335
    assert route.next_hop == {4: "10.251.5.0", 6: "FD00:251:5::"}[family]
    assert route.source_rid == "10.251.5.0"
    assert route.local_preference == 100
    assert route.communities == ["37195:302"]


@pytest.mark.parametrize("kind", ("aspath", "community"))
def test_iosv_summary_tables(kind):
    """IOS summary output carries no communities; the parser must not invent any."""
    table = parse_cisco_ios(
        [(FIXTURES / "cisco-iosv-live" / f"{kind}{family}.txt").read_text() for family in (4, 6)]
    )
    assert [route.prefix for route in table.routes] == [PREFIXES[4], PREFIXES[6]]
    for route in table.routes:
        assert route.as_path == [65000, 13335]
        assert route.active is True
        assert route.communities == []


@pytest.mark.parametrize(
    ("platform", "fixture", "next_hops"),
    [
        ("cisco_xr", "cisco-xr-live", {4: "10.251.4.0", 6: "fd00:251:4::"}),
        ("cisco_nxos", "cisco-nxos-live", {4: "10.251.6.0", 6: "fd00:251:6::"}),
    ],
)
@pytest.mark.parametrize("family", (4, 6))
def test_xr_nxos_route_detail(platform, fixture, next_hops, family):
    table = parse_cisco_ios([(FIXTURES / fixture / f"route{family}.txt").read_text()], platform)
    assert table.count == 1
    route = table.routes[0]
    assert route.prefix == PREFIXES[family]
    assert route.active is True
    assert route.as_path == [65000, 13335]
    assert route.source_as == 13335
    assert route.next_hop == next_hops[family]
    assert route.peer_rid == next_hops[family]
    assert route.source_rid == next_hops[4]
    assert route.local_preference == 100
    assert route.communities == ["37195:302"]


@pytest.mark.parametrize(
    ("platform", "fixture"), [("cisco_xr", "cisco-xr-live"), ("cisco_nxos", "cisco-nxos-live")]
)
@pytest.mark.parametrize("kind", ("aspath", "community"))
def test_xr_nxos_summary_tables(platform, fixture, kind):
    """Summary output carries no communities; the parser must not invent any."""
    table = parse_cisco_ios(
        [(FIXTURES / fixture / f"{kind}{family}.txt").read_text() for family in (4, 6)], platform
    )
    assert [route.prefix for route in table.routes] == [PREFIXES[4], PREFIXES[6]]
    for route in table.routes:
        assert route.as_path == [65000, 13335]
        assert route.active is True
        assert route.communities == []
        assert route.rpki_state == 3


def test_xr_route_best_and_alternate_path():
    table = parse_cisco_ios(
        [(FIXTURES / "cisco-xr-live" / "route4_multipath.txt").read_text()], "cisco_xr"
    )
    best, alternate = table.routes
    assert best.prefix == alternate.prefix == "1.1.1.0/24"
    assert (best.active, alternate.active) == (True, False)
    assert best.as_path == [65000, 13335]
    assert alternate.as_path == [65001, 6939, 13335]
    assert (best.peer_rid, alternate.peer_rid) == ("10.251.4.0", "10.253.4.1")
    assert alternate.source_rid == "10.253.4.1"
    assert (best.med, alternate.med) == (0, 10)
    assert (best.communities, alternate.communities) == (["37195:302"], ["6939:1000"])


@pytest.mark.parametrize("kind", ("aspath", "community"))
def test_xr_summary_best_and_alternate_path(kind):
    table = parse_cisco_ios(
        [(FIXTURES / "cisco-xr-live" / f"{kind}4_multipath.txt").read_text()], "cisco_xr"
    )
    best, alternate = table.routes
    assert best.prefix == alternate.prefix == "8.8.8.0/24"
    assert (best.active, alternate.active) == (True, False)
    assert best.as_path == [65000, 3356, 15169]
    assert alternate.as_path == [65001, 1299, 15169]
    assert (best.med, alternate.med) == (50, 0)


@pytest.mark.parametrize("name", ("route4_empty", "route6_empty", "community4_empty"))
def test_xr_not_found(name):
    text = (FIXTURES / "cisco-xr-live" / f"{name}.txt").read_text()
    assert not command_error(text)
    assert parse_cisco_ios([text], "cisco_xr") is None


def test_xr_command_error():
    text = (FIXTURES / "cisco-xr-live" / "bad.txt").read_text()
    assert command_error(text)
    with pytest.raises(ParsingError):
        parse_cisco_ios([text], "cisco_xr")
