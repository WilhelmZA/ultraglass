"""Cumulus command construction and parser dispatch using shared FRR captures."""

# Standard Library
import shlex
from types import SimpleNamespace
from pathlib import Path

# Third Party
import pytest

# Project
from hyperglass.plugins import OutputPluginManager
from hyperglass.exceptions.public import DeviceCommandError
from hyperglass.defaults.directives import frr, cumulus
from hyperglass.models.config.devices import Device
from hyperglass.execution.drivers._common import Connection
from hyperglass.execution.drivers._construct import Construct
from hyperglass.plugins._builtin.bgp_route_frr import BGPRoutePluginFrr
from hyperglass.plugins._builtin.trace_route_frr import TraceroutePluginFrr

FIXTURES = Path(__file__).parents[2] / "plugins/tests/fixtures"


def device(**kwargs):
    return Device(
        name="cumulus",
        address="192.0.2.10",
        credential={"username": "cumulus", "password": "test"},
        platform="cumulus_linux",
        attrs={"source4": "192.0.2.1", "source6": "2001:db8::1"},
        **kwargs,
    )


def query_for(router, kind, target):
    directive = next(d for d in router.directives if d.query_kind == kind)
    directive.validate_target(target)
    return SimpleNamespace(
        device=router, directive=directive, query_type=directive.id, query_target=target
    )


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize("vrf", [None, "BLUE"])
@pytest.mark.parametrize("family,target", [(4, "1.1.1.0/24"), (6, "2606:4700::/44")])
def test_route_command(structured, vrf, family, target):
    router = device(structured_output=structured, vrf=vrf)
    query = query_for(router, "bgp_route", target)
    context = f"vrf {vrf} " if vrf else ""
    suffix = " json" if structured else ""
    expected = f"show bgp {context}ipv{family} unicast {target}{suffix}"
    assert shlex.split(Construct(router, query).queries()[0]) == [
        "sudo",
        "-n",
        "vtysh",
        "-c",
        expected,
    ]
    assert router.get_device_type() == "cumulus_linux"


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize("vrf", [None, "BLUE"])
@pytest.mark.parametrize(
    "kind,target,selector",
    [
        ("bgp_aspath", "_13335$", "regexp"),
        ("bgp_community", "65000:777", "community"),
    ],
)
def test_pattern_commands(structured, vrf, kind, target, selector):
    router = device(structured_output=structured, vrf=vrf)
    query = query_for(router, kind, target)
    commands = Construct(router, query).queries()
    assert len(commands) == 2
    context = f"vrf {vrf} " if vrf else ""
    suffix = (" json detail" if selector == "community" else " json") if structured else ""
    for family, command in zip((4, 6), commands):
        assert shlex.split(command) == [
            "sudo",
            "-n",
            "vtysh",
            "-c",
            f"show bgp {context}ipv{family} unicast {selector} {target}{suffix}",
        ]


@pytest.mark.parametrize("kind", ["ping", "traceroute"])
@pytest.mark.parametrize("family,target", [(4, "1.1.1.1"), (6, "2606:4700::1111")])
@pytest.mark.parametrize("vrf", [None, "BLUE"])
def test_diagnostics_select_routing_context(kind, family, target, vrf):
    router = device(vrf=vrf)
    query = query_for(router, kind, target)
    args = shlex.split(Construct(router, query).queries()[0])
    assert args[:7] == ["sudo", "-n", "ip", "vrf", "exec", vrf or "default", kind]
    assert f"-{family}" in args
    assert args[-2:] == [router.attrs[f"source{family}"], target]
    assert len(router.directives) == 5


def test_copied_rules_do_not_change_frr():
    assert frr.FRRouting_BGPRoute.rules[0].commands[0].startswith("vtysh")
    assert frr.FRRouting_Ping.rules[0].vrf_commands == []
    assert cumulus.Cumulus_BGPRoute.rules[0] is not frr.FRRouting_BGPRoute.rules[0]


@pytest.mark.parametrize(
    "kind,files",
    [
        ("bgp_route", ["frr-live/route4.txt"]),
        ("bgp_aspath", ["frr-live/aspath4.json"]),
        ("bgp_community", ["frr-live/community4_detail.json", "frr-live/community6_detail.json"]),
        ("traceroute", ["frr-live/trace.txt"]),
    ],
)
@pytest.mark.parametrize("structured", [False, True])
def test_shared_frr_captures_dispatch_through_cumulus(kind, files, structured):
    """Verify shared-parser compatibility; these captures are from FRR, not Cumulus VX."""
    router = device(structured_output=structured)
    targets = {
        "bgp_route": "1.1.1.0/24",
        "bgp_aspath": "13335$",
        "bgp_community": "37195:302",
        "traceroute": "1.1.1.1",
    }
    query = query_for(router, kind, targets[kind])
    manager = OutputPluginManager()
    manager.register(BGPRoutePluginFrr)
    manager.register(TraceroutePluginFrr)
    output = tuple((FIXTURES / name).read_text() for name in files)
    result = manager.execute(output=output, query=query)
    if structured:
        assert result.hops if kind == "traceroute" else result.routes
    else:
        assert result == output


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        "sudo: a password is required",
        "sudo: vtysh: command not found",
        "sudo: user is not allowed to execute this command",
    ],
)
async def test_sudo_failure_is_a_device_error(message):
    router = device()
    connection = SimpleNamespace(device=router)
    with pytest.raises(DeviceCommandError):
        await Connection.response(connection, (message,))
