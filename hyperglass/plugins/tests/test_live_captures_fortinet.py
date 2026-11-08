"""Captured FortiGate-VM64-KVM 7.6.8 lab output (#81)."""

# Standard Library
from pathlib import Path

# Third Party
import pytest

# Project
from hyperglass.plugins import OutputPluginManager
from hyperglass.models.config.devices import Device
from hyperglass.execution.drivers._common import command_error
from hyperglass.plugins._builtin.bgp_route_fortinet import BGPRoutePluginFortinet, parse_fortinet
from hyperglass.plugins._builtin.trace_route_standard import parse_standard_traceroute

FIXTURES = Path(__file__).parent / "fixtures" / "fortinet-live"
PREFIXES = {4: "1.1.1.0/24", 6: "2606:4700::/44"}
NEXT_HOPS = {4: "10.250.1.2", 6: "fd00:250:1::2"}


def _query(target):
    router = Device(
        name="lab-fortigate",
        address="192.0.2.1",
        platform="fortinet",
        structured_output=True,
        credential={"username": "admin", "password": "test"},
        attrs={"source4": "10.250.1.15", "source6": "fd00:250:1::15"},
    )
    directive = next(d for d in router.directives if d.id.endswith("_bgp_route_table__"))
    return type("Query", (), {"device": router, "directive": directive, "query_target": target})()


@pytest.mark.parametrize("family", (4, 6))
def test_route_detail(family):
    table = parse_fortinet((FIXTURES / f"route{family}.txt").read_text())
    assert table.count == 1
    route = table.routes[0]
    assert route.prefix == PREFIXES[family]
    assert route.active is True
    assert route.as_path == [65000, 13335]
    assert route.source_as == 13335
    assert route.next_hop == NEXT_HOPS[family]
    assert route.source_rid == "10.250.1.2"
    assert route.peer_rid == "10.250.1.2"
    assert route.local_preference == 100
    assert route.med == 0
    assert route.communities == ["37195:302"]


@pytest.mark.parametrize("family", (4, 6))
def test_not_found_is_empty(family):
    """A missing prefix is an empty result, not a device error or a route."""
    text = (FIXTURES / f"notfound{family}.txt").read_text()
    assert not command_error((text,))
    manager = OutputPluginManager()
    manager.register(BGPRoutePluginFortinet)
    target = {4: "9.9.9.0/24", 6: "2001:db8::/32"}[family]
    assert manager.execute(output=(text,), query=_query(target)) is None


@pytest.mark.parametrize("family", (4, 6))
def test_trace(family):
    text = (FIXTURES / f"trace{family}.txt").read_text()
    result = parse_standard_traceroute(text, NEXT_HOPS[family], "lab-fortigate")
    assert len(result.hops) == 1
    hop = result.hops[0]
    assert hop.ip_address == NEXT_HOPS[family]
    assert hop.sent_count == {4: 1, 6: 3}[family]
    assert hop.loss_pct == 0


@pytest.mark.parametrize("family", (4, 6))
def test_ping_complete(family):
    """Ping has no structured parser; the capture holds every reply and the summary."""
    text = (FIXTURES / f"ping{family}.txt").read_text()
    assert not command_error((text,))
    assert text.count("bytes from") == 5
    assert "5 packets transmitted, 5 packets received, 0% packet loss" in text
