"""ArcOS command construction and OpenConfig loc-rib parsing."""

# Standard Library
import json
from copy import deepcopy
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
from hyperglass.exceptions.private import ParsingError

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


@pytest.fixture
def instance_output():
    """Include another IPv4 prefix and private instance state in the reference fixture."""
    tree = json.loads((FIXTURES / "route4.json").read_text())
    bgp = tree["network-instance"][0]["protocol"][0]["bgp"]
    routes = bgp["rib"]["afi-safi"][0]["ipv4-unicast"]["loc-rib"]["route"]
    other = deepcopy(routes[0])
    other["prefix"] = other["state"]["prefix"] = "10.1.0.0/16"
    routes.append(other)
    bgp["config"] = {"description": "private-instance-state"}
    return json.dumps(tree)


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
@pytest.mark.parametrize("structured", [False, True])
def test_incomplete_or_unknown_paths_raise(mutation, structured):
    text = mutation((FIXTURES / "route4.json").read_text())
    router = device(structured_output=structured)
    manager = OutputPluginManager()
    manager.register(BGPRoutePluginArcOS)
    with pytest.raises(ParsingError, match="Error parsing ArcOS response data") as error:
        manager.execute(output=(text,), query=query_for(router, "bgp_route", "10.0.0.0/16"))
    assert text not in str(error.value)


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize(
    "target,other",
    [
        ("10.0.0.0/16", "2001:db8::/32"),
        ("2001:db8::/32", "10.0.0.0/16"),
    ],
)
def test_dispatch_filters_both_directives(structured, target, other, instance_output):
    router = device(structured_output=structured)
    manager = OutputPluginManager()
    manager.register(BGPRoutePluginArcOS)
    output = (instance_output,)
    query = query_for(router, "bgp_route", target)
    assert query.directive.id in BGPRoutePluginArcOS().directives
    result = manager.execute(output=output, query=query)
    if structured:
        assert [route.prefix for route in result.routes] == [target]
        response = result.model_dump_json()
    else:
        response = "\n\n".join(result)
        assert f"Prefix: {target}" in response
        assert "Next hop:" in response
    assert other not in response
    assert "10.1.0.0/16" not in response
    assert "private-instance-state" not in response
    assert "ESTABLISHED" not in response
    assert "network-instance" not in response
    assert "neighbor-address" not in response


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize(
    "text",
    [
        "secret device output: permission denied",
        '{"network-instance": [secret device output',
        "null",
        "{}",
        '["secret device output"]',
    ],
)
def test_malformed_output_never_returns_device_text(structured, text):
    from hyperglass.api.error_handlers import app_handler

    router = device(structured_output=structured)
    manager = OutputPluginManager()
    manager.register(BGPRoutePluginArcOS)
    with pytest.raises(ParsingError, match="Error parsing ArcOS response data") as error:
        manager.execute(output=(text,), query=query_for(router, "bgp_route", "10.0.0.0/16"))
    assert "secret device output" not in str(error.value)
    response = app_handler(
        SimpleNamespace(method="POST", url=SimpleNamespace(path="/api/query")), error.value
    )
    assert "secret device output" not in json.dumps(response.content)
    assert response.content["output"] == "Error parsing ArcOS response data"


@pytest.mark.parametrize("structured", [False, True])
def test_dispatch_absent_target_never_returns_instance(structured, instance_output):
    router = device(structured_output=structured)
    manager = OutputPluginManager()
    manager.register(BGPRoutePluginArcOS)
    result = manager.execute(
        output=(instance_output,),
        query=query_for(router, "bgp_route", "203.0.113.0/24"),
    )
    if structured:
        assert result.count == 0 and result.routes == []
    else:
        assert result == ("No route found.",)
