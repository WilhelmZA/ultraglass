"""Captured Cisco IOS-XR, NX-OS and IOSv lab output (#99, #100)."""

# Standard Library
from pathlib import Path

# Third Party
import pytest

# Project
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
