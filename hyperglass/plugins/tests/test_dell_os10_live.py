"""Replay OS10 10.6.1 captures from default and named routing contexts."""

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
from hyperglass.plugins._builtin.trace_route_standard import TraceroutePluginStandard

FIXTURES = Path(__file__).parent / "fixtures" / "dell-os10-live"
COMMANDS = {
    row["file"]: row["command"] for row in json.loads((FIXTURES / "manifest.json").read_text())
}
CONTEXTS = {
    "default": (1, 13335, "1.0.0.0/24", "2606:4700:4700::/48"),
    "lab": (2, 64497, "198.51.100.0/24", "2001:db8:100::/48"),
}


def query_for(context, kind, target, structured=True):
    index = CONTEXTS[context][0]
    device = Device(
        name=f"os10-{context}",
        address="192.0.2.1",
        credential={"username": "reader", "password": "test"},
        platform="dell_os10",
        structured_output=structured,
        vrf="LAB" if context == "lab" else None,
        attrs={"source4": f"10.250.{index}.1", "source6": f"fd00:250:{index}::1"},
    )
    directive = next(d for d in device.directives if d.query_kind == kind)
    return SimpleNamespace(
        device=device, directive=directive, query_type=directive.id, query_target=target
    )


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("family", [4, 6])
def test_live_route_fields(context, family):
    index, asn, prefix4, prefix6 = CONTEXTS[context]
    prefix = prefix4 if family == 4 else prefix6
    query = query_for(context, "bgp_route", prefix)
    file = f"{context}-route{family}.txt"
    assert Construct(query.device, query).queries() == [COMMANDS[file]]
    result = BGPRoutePluginDell().process(output=((FIXTURES / file).read_text(),), query=query)
    assert isinstance(result, BGPRouteTable)
    assert result.vrf == ("LAB" if context == "lab" else "default")
    assert result.count == len(result.routes) == 1
    route = result.routes[0]
    assert route.prefix == prefix
    assert route.as_path == [65000, asn]
    assert route.next_hop == (f"10.250.{index}.2" if family == 4 else f"fd00:250:{index}::2")
    assert route.peer_rid == route.source_rid == f"10.250.{index}.2"
    assert route.active is True
    assert route.communities == ["65000:777"]
    assert (route.med, route.local_preference, route.weight) == (42, 100, 0)


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("structured", [False, True])
def test_live_community_summaries_preserve_both_families(context, structured):
    query = query_for(context, "bgp_community", "65000:777", structured)
    files = [f"{context}-community{family}.txt" for family in (4, 6)]
    assert Construct(query.device, query).queries() == [COMMANDS[file] for file in files]
    output = tuple((FIXTURES / file).read_text() for file in files)
    manager = OutputPluginManager()
    manager.register(BGPRoutePluginDell)
    assert manager.execute(output=output, query=query) == output
    _, asn, prefix4, prefix6 = CONTEXTS[context]
    for text, prefix in zip(output, (prefix4, prefix6)):
        assert prefix in text and f"65000 {asn} i" in text


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("family", [4, 6])
def test_live_ping_commands(context, family):
    index = CONTEXTS[context][0]
    target = f"10.250.{index}.2" if family == 4 else f"fd00:250:{index}::2"
    query = query_for(context, "ping", target)
    file = f"{context}-ping{family}.txt"
    assert Construct(query.device, query).queries() == [COMMANDS[file]]
    assert "5 packets transmitted, 5 received, 0% packet loss" in (FIXTURES / file).read_text()


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("family", [4, 6])
@pytest.mark.parametrize("structured", [False, True])
def test_live_traceroute(context, family, structured):
    index = CONTEXTS[context][0]
    target = f"10.250.{index}.1" if family == 4 else f"fd00:250:{index}::1"
    query = query_for(context, "traceroute", target, structured)
    file = f"{context}-trace{family}.txt"
    assert Construct(query.device, query).queries() == [COMMANDS[file]]
    output = ((FIXTURES / file).read_text(),)
    result = TraceroutePluginStandard().process(output=output, query=query)
    if structured:
        assert len(result.hops) == 1
        hop = result.hops[0]
        assert hop.ip_address == target and hop.hop_number == 1
        assert hop.rtt1 is not None and hop.rtt2 is None and hop.rtt3 is None
        assert hop.sent_count == 1
    else:
        assert result == output


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("family", [4, 6])
def test_other_vrf_prefix_is_absent(context, family):
    other = CONTEXTS["lab" if context == "default" else "default"]
    query = query_for(context, "bgp_route", other[2 if family == 4 else 3])
    file = f"{context}-negative{family}.txt"
    assert Construct(query.device, query).queries() == [COMMANDS[file]]
    output = ((FIXTURES / file).read_text(),)
    assert output[0].strip() == "%Error: Prefix does not exist."
    assert BGPRoutePluginDell().process(output=output, query=query) == output


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("family", [4, 6])
def test_live_routes_stay_text_when_requested(context, family):
    query = query_for(context, "bgp_route", CONTEXTS[context][2 if family == 4 else 3], False)
    output = ((FIXTURES / f"{context}-route{family}.txt").read_text(),)
    assert BGPRoutePluginDell().process(output=output, query=query) == output


@pytest.mark.parametrize("damage", ["missing_hop", "invalid_metric", "truncated_path"])
def test_malformed_live_route_stays_text(damage):
    text = (FIXTURES / "default-route4.txt").read_text()
    if damage == "missing_hop":
        text = text.replace("Next-Hop", "Missing-Hop")
    elif damage == "invalid_metric":
        text = text.replace("Metric 42", "Metric unknown")
    else:
        text = text.replace("1 available", "2 available")
    output = (text,)
    query = query_for("default", "bgp_route", "1.0.0.0/24")
    assert BGPRoutePluginDell().process(output=output, query=query) == output
