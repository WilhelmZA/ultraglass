"""OcNOS command-reference forms and attributed parser examples."""

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
from hyperglass.execution.drivers.ssh_netmiko import collect_commands
from hyperglass.plugins._builtin.bgp_route_ocnos import BGPRoutePluginOcNOS, parse_ocnos
from hyperglass.plugins._builtin.trace_route_standard import TraceroutePluginStandard

FIXTURES = Path(__file__).parents[2] / "plugins/tests/fixtures/ocnos-reference"


def device(**kwargs):
    return Device(
        name="ocnos",
        address="192.0.2.1",
        platform="ipinfusion_ocnos",
        credential={"username": "reader", "password": "test"},
        **kwargs,
    )


def query_for(router, kind, target):
    directive = next(d for d in router.directives if d.query_kind == kind)
    return SimpleNamespace(
        device=router, directive=directive, query_target=target, query_type=directive.id
    )


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize(
    "kind,target,expected",
    [
        ("bgp_route", "1.1.1.0/24", ["show bgp ipv4 unicast 1.1.1.0/24"]),
        ("bgp_route", "2001:db8::/32", ["show bgp ipv6 unicast 2001:db8::/32"]),
        (
            "bgp_aspath",
            "_13335$",
            ["show bgp ipv4 unicast regexp _13335$", "show bgp ipv6 unicast regexp _13335$"],
        ),
        ("bgp_community", "65000:777", ["show ip bgp community 65000:777"]),
        ("ping", "1.1.1.1", ["ping ip 1.1.1.1 count 5"]),
        ("ping", "2001:db8::1", ["ping ipv6 2001:db8::1 count 5"]),
        ("traceroute", "1.1.1.1", ["traceroute 1.1.1.1"]),
        ("traceroute", "2001:db8::1", ["traceroute ipv6 2001:db8::1"]),
    ],
)
def test_commands(structured, kind, target, expected):
    router = device(structured_output=structured)
    assert Construct(router, query_for(router, kind, target)).queries() == expected
    assert router.get_device_type() == "ipinfusion_ocnos"


def test_vrf_only_offers_verified_diagnostics():
    router = device(vrf="BLUE")
    assert {d.query_kind for d in router.directives} == {"ping", "traceroute"}
    for kind in ("ping", "traceroute"):
        for target in ("1.1.1.1", "2001:db8::1"):
            command = Construct(router, query_for(router, kind, target)).queries()[0]
            assert command.endswith("vrf BLUE")


@pytest.mark.parametrize("family,count", [(4, 2), (6, 1)])
def test_reference_paths_and_multiline_best_flag(family, count):
    params = use_state("params")
    params.structured.communities.mode = "deny"
    params.structured.communities.items = []
    use_state().redis.set("params", params)
    result = parse_ocnos((FIXTURES / f"route{family}.txt").read_text())
    assert result.count == count
    assert result.routes[0].active
    assert all(r.age == -1 and r.rpki_state == 3 for r in result.routes)
    if family == 6:
        assert result.routes[0].communities == ["37721:2000"]
        assert result.routes[0].weight == 32768
    else:
        assert not result.routes[1].active


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize(
    "kind,file,target",
    [
        ("bgp_route", "route4.txt", "22.22.22.22/32"),
        ("traceroute", "trace4.txt", "10.10.100.126"),
    ],
)
def test_parser_dispatch(structured, kind, file, target):
    router = device(structured_output=structured)
    manager = OutputPluginManager()
    manager.register(BGPRoutePluginOcNOS)
    manager.register(TraceroutePluginStandard)
    output = ((FIXTURES / file).read_text(),)
    result = manager.execute(output=output, query=query_for(router, kind, target))
    if structured:
        assert result.routes if kind == "bgp_route" else result.hops
    else:
        assert result == output


def test_truncated_detail_stays_text():
    text = (FIXTURES / "route4.txt").read_text().replace("2 available", "3 available")
    router = device(structured_output=True)
    assert BGPRoutePluginOcNOS().process(
        output=(text,), query=query_for(router, "bgp_route", "22.22.22.22/32")
    ) == (text,)


def test_driver_enters_privileged_mode_before_diagnostics():
    events = []

    class Session:
        def enable(self):
            events.append("enable")

        def send_command(self, command, **kwargs):
            events.append(command)
            return "reply"

        def disconnect(self):
            events.append("disconnect")

    collect_commands(Session(), "ipinfusion_ocnos", ["ping ip 1.1.1.1 count 5"], 10)
    assert events == ["enable", "ping ip 1.1.1.1 count 5", "disconnect"]
