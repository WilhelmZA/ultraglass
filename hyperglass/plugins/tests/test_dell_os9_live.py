"""Replay OS9 9.13 captures and verify commands against the live manifest."""

# Standard Library
import json
from types import SimpleNamespace
from pathlib import Path

# Third Party
import pytest

# Project
from hyperglass.plugins import OutputPluginManager
from hyperglass.models.config.devices import Device
from hyperglass.models.data.bgp_route import BGPRouteTable
from hyperglass.execution.drivers._construct import Construct
from hyperglass.plugins._builtin.bgp_route_dell import BGPRoutePluginDell
from hyperglass.plugins._builtin.trace_route_os9 import TraceroutePluginOS9

FIXTURES = Path(__file__).parent / "fixtures" / "dell-os9-live"
COMMANDS = {
    row["file"]: row["command"] for row in json.loads((FIXTURES / "manifest.json").read_text())
}
CONTEXTS = {
    "default": (13335, "1.0.0.0/24", "2606:4700:4700::/48", "10.251.9.2", "fd00:251:9::2"),
    "lab": (64497, "198.51.100.0/24", "2001:db8:100::/48", "10.254.2.2", "fd00:254:2::2"),
}


def query_for(context, kind, target, structured=True):
    device = Device(
        name=f"os9-{context}",
        address="192.0.2.1",
        credential={"username": "reader", "password": "test"},
        platform="dell_force10",
        structured_output=structured,
        vrf="LAB" if context == "lab" else None,
    )
    directive = next(d for d in device.directives if d.query_kind == kind)
    return SimpleNamespace(
        device=device, directive=directive, query_type=directive.id, query_target=target
    )


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("family", [4, 6])
def test_live_route_fields(context, family):
    asn, prefix4, prefix6, hop4, hop6 = CONTEXTS[context]
    prefix, hop = (prefix4, hop4) if family == 4 else (prefix6, hop6)
    query = query_for(context, "bgp_route", prefix)
    file = f"{context}-route{family}.txt"
    output = ((FIXTURES / file).read_text(),)
    assert Construct(query.device, query).queries() == [COMMANDS[file]]
    result = BGPRoutePluginDell().process(output=output, query=query)
    assert isinstance(result, BGPRouteTable)
    assert result.vrf == ("LAB" if context == "lab" else "default")
    assert result.count == 1
    route = result.routes[0]
    assert route.prefix == prefix
    assert route.as_path == [65000, asn]
    assert route.next_hop == hop
    assert route.active is True
    assert route.communities == ["65000:777"]
    assert route.med == 4294967295
    assert route.local_preference == 100
    assert route.weight == 0
    assert route.peer_rid == route.source_rid == hop4


@pytest.mark.parametrize("context", CONTEXTS)
def test_live_search_commands_and_text(context):
    for kind, target, files in [
        ("bgp_aspath", "_65000_", [f"{context}-aspath.txt"]),
        ("bgp_community", "65000:777", [f"{context}-community4.txt", f"{context}-community6.txt"]),
    ]:
        query = query_for(context, kind, target)
        assert Construct(query.device, query).queries() == [COMMANDS[file] for file in files]
        output = tuple((FIXTURES / file).read_text() for file in files)
        manager = OutputPluginManager()
        manager.register(BGPRoutePluginDell)
        assert manager.execute(output=output, query=query) == output


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("family", [4, 6])
def test_live_ping_commands(context, family):
    target = CONTEXTS[context][3 if family == 4 else 4]
    query = query_for(context, "ping", target)
    file = f"{context}-ping{family}.txt"
    assert Construct(query.device, query).queries() == [COMMANDS[file]]
    assert "100.0 percent (5/5)" in (FIXTURES / file).read_text()


@pytest.mark.parametrize("family,target", [(4, "10.251.9.1"), (6, "fd00:251:9::1")])
@pytest.mark.parametrize("structured", [False, True])
def test_live_traceroute(family, target, structured):
    query = query_for("default", "traceroute", target, structured)
    file = f"default-trace{family}.txt"
    output = ((FIXTURES / file).read_text(),)
    assert Construct(query.device, query).queries() == [COMMANDS[file]]
    result = TraceroutePluginOS9().process(output=output, query=query)
    if structured:
        assert len(result.hops) == 1
        assert result.hops[0].ip_address == target
        assert all(getattr(result.hops[0], f"rtt{i}") is not None for i in (1, 2, 3))
    else:
        assert result == output


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("family", [4, 6])
def test_live_routes_stay_text_when_requested(context, family):
    query = query_for(context, "bgp_route", CONTEXTS[context][1 if family == 4 else 2], False)
    output = ((FIXTURES / f"{context}-route{family}.txt").read_text(),)
    assert BGPRoutePluginDell().process(output=output, query=query) == output


@pytest.mark.parametrize("damage", ["missing_hop", "invalid_metric", "truncated_path"])
def test_malformed_live_route_stays_text(damage):
    text = (FIXTURES / "default-route4.txt").read_text()
    if damage == "missing_hop":
        text = text.replace("Next-Hop", "Missing-Hop")
    elif damage == "invalid_metric":
        text = text.replace("4294967295 (Default)", "unknown (Default)")
    else:
        text = text.replace("1 available", "2 available")
    output = (text,)
    query = query_for("default", "bgp_route", "1.0.0.0/24")
    assert BGPRoutePluginDell().process(output=output, query=query) == output


def test_wrapped_communities_stop_before_other_attributes():
    text = (FIXTURES / "default-route4.txt").read_text()
    text = text.replace(
        "65000:777", "65000:777 65000:778\n  65000:779\n Extended Communities : 65000:999"
    )
    query = query_for("default", "bgp_route", "1.0.0.0/24")
    result = BGPRoutePluginDell().process(output=(text,), query=query)
    assert isinstance(result, BGPRouteTable)
    assert result.routes[0].communities == ["65000:777", "65000:778", "65000:779"]
