"""Replay Cumulus VX 5.4 captures from default and LAB routing contexts."""

# Standard Library
import json
from types import SimpleNamespace
from pathlib import Path

# Third Party
import pytest

# Project
from hyperglass.plugins import OutputPluginManager
from hyperglass.exceptions.private import ParsingError
from hyperglass.models.config.devices import Device
from hyperglass.plugins._builtin.bgp_route_frr import BGPRoutePluginFrr, parse_frr
from hyperglass.plugins._builtin.trace_route_frr import TraceroutePluginFrr

FIXTURES = Path(__file__).parent / "fixtures" / "cumulus-live"
CONTEXTS = {
    "default": (1, 13335, "1.0.0.0/24", "2606:4700:4700::/48"),
    "lab": (2, 64497, "198.51.100.0/24", "2001:db8:100::/48"),
}


def query_for(context, kind, structured=True):
    link, _, _, _ = CONTEXTS[context]
    device = Device(
        name=f"cumulus-{context}",
        address="192.0.2.10",
        credential={"username": "cumulus", "password": "test"},
        platform="cumulus_linux",
        structured_output=structured,
        vrf="LAB" if context == "lab" else None,
        attrs={"source4": f"10.252.{link}.1", "source6": f"2001:db8:252:{link}::1"},
    )
    directive = next(d for d in device.directives if d.query_kind == kind)
    return SimpleNamespace(
        device=device, directive=directive, query_type=directive.id, query_target=f"10.252.{link}.1"
    )


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("kind", ["route", "aspath", "community"])
def test_live_bgp_fields_and_vrf(context, kind):
    link, asn, prefix4, prefix6 = CONTEXTS[context]
    query = query_for(context, f"bgp_{kind}")
    plugin = BGPRoutePluginFrr()
    captures = [(FIXTURES / f"{context}-{kind}{family}.json").read_text() for family in (4, 6)]
    result = plugin.process(output=tuple(captures), query=query)

    assert result.vrf == ("LAB" if context == "lab" else "default")
    assert result.count == 2
    assert {route.prefix for route in result.routes} == {prefix4, prefix6}
    for route in result.routes:
        assert route.as_path == [64999, asn]
        assert route.active is True
        expected_hop = f"2001:db8:252:{link}::2" if ":" in route.prefix else f"10.252.{link}.2"
        assert route.next_hop == expected_hop
        if kind in ("route", "community"):
            assert set(route.communities) == {"65000:777", "65000:777:1"}


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("family", [4, 6])
def test_live_traceroute_reaches_selected_vrf_address(context, family):
    link = CONTEXTS[context][0]
    query = query_for(context, "traceroute")
    query.query_target = f"10.252.{link}.1" if family == 4 else f"2001:db8:252:{link}::1"
    capture = (FIXTURES / f"{context}-trace{family}.txt").read_text()
    result = TraceroutePluginFrr().process(output=(capture,), query=query)

    assert len(result.hops) == 1
    assert str(result.hops[0].ip_address) == (
        f"10.252.{link}.1" if family == 4 else f"2001:db8:252:{link}::1"
    )
    assert result.hops[0].rtt1 is not None


@pytest.mark.parametrize("context", CONTEXTS)
@pytest.mark.parametrize("kind", ["route", "aspath", "community", "trace"])
def test_live_text_output_stays_text(context, kind):
    query = query_for(context, "traceroute" if kind == "trace" else f"bgp_{kind}", False)
    manager = OutputPluginManager()
    manager.register(BGPRoutePluginFrr)
    manager.register(TraceroutePluginFrr)
    captures = tuple((FIXTURES / f"{context}-{kind}{family}.txt").read_text() for family in (4, 6))
    assert manager.execute(output=captures, query=query) == captures


@pytest.mark.parametrize(
    "damage", ["missing_next_hop", "wrong_header_prefix", "header_has_path_field"]
)
def test_community_metadata_handling_does_not_hide_malformed_paths(damage):
    data = json.loads((FIXTURES / "default-community4.json").read_text())
    paths = data["routes"]["1.0.0.0/24"]
    if damage == "missing_next_hop":
        del paths[1]["nexthops"]
    elif damage == "wrong_header_prefix":
        paths[0]["prefix"] = "192.0.2.0/24"
    else:
        paths[0]["valid"] = True
    with pytest.raises(ParsingError):
        parse_frr((json.dumps(data),))
