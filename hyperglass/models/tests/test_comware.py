"""Comware 7 commands and documented output formats."""

# Standard Library
from types import SimpleNamespace
from pathlib import Path

# Third Party
import pytest

# Project
from hyperglass.plugins import OutputPluginManager
from hyperglass.models.config.devices import Device
from hyperglass.execution.drivers._construct import Construct
from hyperglass.plugins._builtin.bgp_route_comware import BGPRoutePluginComware, parse_comware
from hyperglass.plugins._builtin.trace_route_standard import TraceroutePluginStandard

FIXTURES = Path(__file__).parents[2] / "plugins/tests/fixtures/comware-reference"


def device(**kwargs):
    return Device(
        name="comware",
        address="192.0.2.1",
        platform="hp_comware",
        credential={"username": "reader", "password": "test"},
        attrs={"source4": "192.0.2.1", "source6": "2001:db8::1"},
        **kwargs,
    )


def query_for(router, kind, target):
    directive = next(d for d in router.directives if d.query_kind == kind)
    return SimpleNamespace(
        device=router, directive=directive, query_target=target, query_type=directive.id
    )


@pytest.mark.parametrize("structured", [True, False])
@pytest.mark.parametrize("vrf", [None, "BLUE"])
@pytest.mark.parametrize(
    "target,expected,family",
    [
        ("1.1.1.0/24", "1.1.1.0 24", 4),
        ("1.1.1.1", "1.1.1.1 32", 4),
        ("2606:4700::/44", "2606:4700:: 44", 6),
        ("2001:db8::1", "2001:db8::1 128", 6),
    ],
)
def test_exact_route_commands(structured, vrf, target, expected, family):
    router = device(structured_output=structured, vrf=vrf)
    query = query_for(router, "bgp_route", target)
    context = f"vpn-instance {vrf} " if vrf else ""
    assert Construct(router, query).queries() == [
        f"display bgp routing-table ipv{family} unicast {context}{expected}"
    ]
    assert router.get_device_type() == "hp_comware"
    assert {d.query_kind for d in router.directives} == {"bgp_route", "ping", "traceroute"}


@pytest.mark.parametrize("vrf", [None, "BLUE"])
@pytest.mark.parametrize("kind", ["ping", "traceroute"])
@pytest.mark.parametrize("target,family", [("1.1.1.1", 4), ("2001:db8::1", 6)])
def test_diagnostics(vrf, kind, target, family):
    router = device(vrf=vrf)
    query = query_for(router, kind, target)
    command = Construct(router, query).queries()[0]
    assert ("-vpn-instance BLUE" in command) is bool(vrf)
    assert ("ipv6" in command) is (family == 6)
    assert command.endswith(target)
    if family == 6 and kind == "traceroute":
        assert "-a" not in command.split()
    else:
        assert f"-a {router.attrs[f'source{family}']}" in command


@pytest.mark.parametrize("family,prefix", [(4, "10.2.1.0/24"), (6, "2::/64")])
def test_documented_detail_keeps_all_paths(family, prefix):
    result = parse_comware((FIXTURES / f"route{family}.txt").read_text(), "BLUE")
    assert result.vrf == "BLUE"
    assert result.count == 2
    assert [r.active for r in result.routes] == [True, False]
    assert all(r.prefix == prefix and r.rpki_state == 3 and r.age == -1 for r in result.routes)
    assert result.routes[1].as_path == ([200] if family == 4 else [100])
    assert result.routes[1].source_rid == ("192.168.100.2" if family == 4 else "192.168.1.136")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda s: s.replace("Paths: 2", "Paths: 3"),
        lambda s: s.replace("AS-path         : 200", "AS-path         : {200,300}"),
        lambda s: s.replace("Original nexthop: 10.2.1.2", "Original nexthop: invalid"),
    ],
)
def test_unrecognized_or_truncated_detail_stays_text(mutation):
    router = device(structured_output=True)
    output = (mutation((FIXTURES / "route4.txt").read_text()),)
    assert (
        BGPRoutePluginComware().process(
            output=output, query=query_for(router, "bgp_route", "10.2.1.0/24")
        )
        == output
    )


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize(
    "kind,file,target",
    [
        ("bgp_route", "route4.txt", "10.2.1.0/24"),
        ("traceroute", "trace6.txt", "2001:3::2"),
    ],
)
def test_dispatch(kind, file, target, structured):
    router = device(structured_output=structured)
    manager = OutputPluginManager()
    manager.register(BGPRoutePluginComware)
    manager.register(TraceroutePluginStandard)
    output = ((FIXTURES / file).read_text(),)
    result = manager.execute(output=output, query=query_for(router, kind, target))
    if structured:
        assert result.routes if kind == "bgp_route" else result.hops
    else:
        assert result == output
