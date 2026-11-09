"""ArcOS command construction and OpenConfig loc-rib parsing."""

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
from hyperglass.plugins._builtin.bgp_route_arcos import BGPRoutePluginArcOS, parse_arcos

FIXTURES = Path(__file__).parents[2] / "plugins/tests/fixtures/arcos-reference"
SHOW = "echo 'show network-instance default protocol BGP BGP | display json' | confd_cli -C"


def device(**kwargs):
    return Device(
        name="arcos",
        address="192.0.2.1",
        platform="arrcus_arcos",
        credential={"username": "reader", "password": "test"},
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
    "target,expected",
    [
        ("1.1.1.1", "1.1.1.1/32"),
        ("1.1.1.0/24", "1.1.1.0/24"),
        ("2001:db8::1", "2001:db8::1/128"),
        ("2001:db8::/32", "2001:db8::/32"),
    ],
)
def test_route_command(structured, vrf, target, expected):
    router = device(structured_output=structured, vrf=vrf)
    instance = vrf or "default"
    constructed = Construct(router, query_for(router, "bgp_route", target))
    assert constructed.queries() == [
        f"echo 'show network-instance {instance} protocol BGP BGP | display json' | confd_cli -C"
    ]
    assert constructed.target == expected
    assert router.get_device_type() == "linux_ssh"


def test_queries_match_documented_capabilities():
    router = device(structured_output=True)
    assert {d.query_kind for d in router.directives} == {"bgp_route"}
    assert {d.query_kind for d in device(vrf="BLUE").directives} == {"bgp_route"}
    assert Construct(router, query_for(router, "bgp_route", "10.0.0.0/16")).queries() == [SHOW]
    assert (
        Device(
            name="arcos-alias",
            address="192.0.2.1",
            platform="arcos",
            credential={"username": "reader", "password": "test"},
        ).platform
        == "arrcus_arcos"
    )


def test_reference_ipv4_filters_other_prefixes_and_neighbors():
    params = use_state("params")
    params.structured.communities.mode = "deny"
    params.structured.communities.items = []
    use_state().redis.set("params", params)
    table = parse_arcos((FIXTURES / "route4.json").read_text(), "10.0.0.0/16")
    assert table.count == 1
    route = table.routes[0]
    assert route.prefix == "10.0.0.0/16"
    assert route.next_hop == "192.0.2.1"
    assert route.active and route.as_path == [65000, 13335]
    assert route.local_preference == 100 and route.med == 0 and route.weight == 0
    assert route.communities == ["65000:777"]
    assert route.peer_rid == "192.0.2.1"
    assert route.source_rid == "192.0.2.1" and route.age == -1 and route.rpki_state == 3


def test_reference_ipv6_and_confd_preamble():
    body = (FIXTURES / "route4.json").read_text()
    table = parse_arcos("Commit complete.\n" + body, "2001:db8::/32", "BLUE")
    assert table.vrf == "BLUE" and table.count == 1
    assert table.routes[0].prefix == "2001:db8::/32"
    assert table.routes[0].next_hop == "2001:db8::1"
    assert table.routes[0].as_path == [65000]


def test_attr_index_path():
    table = parse_arcos((FIXTURES / "route4-attrset.json").read_text(), "10.0.0.0/16")
    route = table.routes[0]
    assert table.count == 1
    assert route.next_hop == "192.0.2.8"
    assert route.as_path == [65100, 13335]
    assert route.med == 50 and route.local_preference == 200
    assert route.communities == ["65100:1", "65100:2"]


def test_missing_prefix_is_empty_table():
    table = parse_arcos((FIXTURES / "route4.json").read_text(), "203.0.113.0/24")
    assert table.count == 0 and table.routes == []


def test_synthetic_multipath_and_asdot():
    table = parse_arcos((FIXTURES / "route4-multipath.json").read_text(), "10.0.0.0/16")
    assert table.count == 2
    assert [route.active for route in table.routes] == [True, False]
    assert table.routes[0].as_path == [1, 65000]
    assert table.routes[1].next_hop == "192.0.2.2"
    assert table.routes[1].as_path == [65546, 65000]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda s: s.replace('"next-hop": "192.0.2.1"', '"next-hop": "not-an-ip"'),
        lambda s: s.replace('"type": "AS_SEQ"', '"type": "AS_SET"'),
        lambda s: s.replace("[65000, 13335]", '["bad"]'),
    ],
)
def test_incomplete_or_unknown_paths_stay_text(mutation):
    text = mutation((FIXTURES / "route4.json").read_text())
    router = device(structured_output=True)
    output = (text,)
    assert (
        BGPRoutePluginArcOS().process(
            output=output, query=query_for(router, "bgp_route", "10.0.0.0/16")
        )
        == output
    )


@pytest.mark.parametrize("structured", [False, True])
def test_dispatch(structured):
    router = device(structured_output=structured)
    manager = OutputPluginManager()
    manager.register(BGPRoutePluginArcOS)
    output = ((FIXTURES / "route4.json").read_text(),)
    result = manager.execute(output=output, query=query_for(router, "bgp_route", "10.0.0.0/16"))
    if structured:
        assert result.routes and result.routes[0].prefix == "10.0.0.0/16"
    else:
        assert result == output
