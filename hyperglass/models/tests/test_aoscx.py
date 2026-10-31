"""AOS-CX command construction and reference detail parsing."""

# Standard Library
from types import SimpleNamespace
from pathlib import Path

# Third Party
import pytest

# Project
from hyperglass.state import use_state
from hyperglass.plugins import OutputPluginManager
from hyperglass.models.config.devices import Device
from hyperglass.execution.drivers._construct import Construct
from hyperglass.plugins._builtin.bgp_route_aoscx import BGPRoutePluginAOSCX, parse_aoscx
from hyperglass.plugins._builtin.trace_route_standard import TraceroutePluginStandard

FIXTURES = Path(__file__).parents[2] / "plugins/tests/fixtures/aoscx-reference"


def device(**kwargs):
    return Device(
        name="aoscx",
        address="192.0.2.1",
        platform="aruba_aoscx",
        credential={"username": "reader", "password": "test"},
        attrs={"source4": "192.0.2.1", "source6": "2001:db8::1"},
        **kwargs,
    )


def query_for(router, kind, target):
    directive = next(d for d in router.directives if d.query_kind == kind)
    return SimpleNamespace(
        device=router, directive=directive, query_target=target, query_type=directive.id
    )


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize("vrf", [None, "BLUE"])
@pytest.mark.parametrize(
    "target,expected,family",
    [
        ("1.1.1.1", "1.1.1.1/32", 4),
        ("1.1.1.0/24", "1.1.1.0/24", 4),
        ("2001:db8::1", "2001:db8::1/128", 6),
        ("2001:db8::/32", "2001:db8::/32", 6),
    ],
)
def test_route_command(structured, vrf, target, expected, family):
    router = device(structured_output=structured, vrf=vrf)
    context = f"vrf {vrf} " if vrf else ""
    assert Construct(router, query_for(router, "bgp_route", target)).queries() == [
        f"show bgp {context}ipv{family} unicast {expected}"
    ]
    assert router.get_device_type() == "aruba_aoscx"


@pytest.mark.parametrize("vrf", [None, "BLUE"])
@pytest.mark.parametrize("kind", ["ping", "traceroute"])
@pytest.mark.parametrize("family,target", [(4, "1.1.1.1"), (6, "2001:db8::1")])
def test_diagnostics(vrf, kind, family, target):
    router = device(vrf=vrf)
    name = kind + ("6" if family == 6 else "")
    options = "repetitions 5" if kind == "ping" else "probes 1 timeout 1"
    context = f"vrf {vrf} " if vrf else ""
    assert Construct(router, query_for(router, kind, target)).queries() == [
        f"{name} {target} {options} {context}source {router.attrs[f'source{family}']}"
    ]


def test_queries_match_documented_capabilities():
    router = device(structured_output=True)
    assert {d.query_kind for d in router.directives} == {
        "bgp_route",
        "bgp_community",
        "ping",
        "traceroute",
    }
    assert Construct(router, query_for(router, "bgp_community", "65000:777")).queries() == [
        "show bgp ipv4 unicast community 65000:777",
        "show bgp ipv6 unicast community 65000:777",
    ]
    assert {d.query_kind for d in device(vrf="BLUE").directives} == {
        "bgp_route",
        "ping",
        "traceroute",
    }


def test_reference_labels_and_wrapped_communities():
    params = use_state("params")
    params.structured.communities.mode = "deny"
    params.structured.communities.items = []
    use_state().redis.set("params", params)
    table = parse_aoscx((FIXTURES / "route4.txt").read_text())
    assert table.count == 1
    route = table.routes[0]
    assert route.prefix == "10.0.0.0/16"
    assert route.next_hop == "1.1.1.1"
    assert route.active and route.as_path == [1]
    assert route.local_preference == 100 and route.med == 0 and route.weight == 0
    assert len(route.communities) == 12
    assert route.communities[-1] == "50:1"
    assert route.source_rid == "" and route.age == -1 and route.rpki_state == 3


def test_synthetic_ipv6_multipath_and_asdot():
    first = (FIXTURES / "route4.txt").read_text()
    first = first.replace("10.0.0.0/16", "2001:db8::/32").replace("1.1.1.1", "2001:db8::1")
    first = first.replace("AS-Path                  : 1", "AS-Path                  : 1.10 65000")
    second = first.replace("Best                     : Yes", "Best                     : No")
    second = second.replace("2001:db8::1", "2001:db8::2")
    table = parse_aoscx(first + second[second.index("    Network") :], "BLUE")
    assert table.vrf == "BLUE" and table.count == 2
    assert [r.active for r in table.routes] == [True, False]
    assert table.routes[0].as_path == [65546, 65000]
    assert table.routes[1].next_hop == "2001:db8::2"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda s: s[: s.index("    Extd. Communities")],
        lambda s: s.replace("AS-Path                  : 1", "AS-Path                  : {1,2}"),
        lambda s: s.replace(
            "Nexthop                     : 1.1.1.1", "Nexthop                     : bad"
        ),
    ],
)
def test_incomplete_or_unknown_paths_stay_text(mutation):
    text = (FIXTURES / "route4.txt").read_text()
    # One bad path must prevent a misleading partial table.
    output = (text + mutation(text[text.index("    Network") :]),)
    router = device(structured_output=True)
    assert (
        BGPRoutePluginAOSCX().process(
            output=output, query=query_for(router, "bgp_route", "10.0.0.0/16")
        )
        == output
    )


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize(
    "kind,file,target",
    [
        ("bgp_route", "route4.txt", "10.0.0.0/16"),
        ("traceroute", "trace4.txt", "10.0.10.1"),
        ("traceroute", "trace6.txt", "2001::2"),
    ],
)
def test_dispatch(structured, kind, file, target):
    router = device(structured_output=structured)
    manager = OutputPluginManager()
    manager.register(BGPRoutePluginAOSCX)
    manager.register(TraceroutePluginStandard)
    output = ((FIXTURES / file).read_text(),)
    result = manager.execute(output=output, query=query_for(router, kind, target))
    if structured:
        assert result.routes if kind == "bgp_route" else result.hops
        if kind == "traceroute":
            assert result.hops[0].rtt1 == (0.002 if file == "trace4.txt" else 0.4331)
    else:
        assert result == output
