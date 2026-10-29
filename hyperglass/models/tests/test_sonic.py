"""Community SONiC platform and directive set (#76)."""

# Standard Library
import shlex
from types import SimpleNamespace

# Third Party
import pytest

# Project
from hyperglass.models.config.devices import Device
from hyperglass.execution.drivers._construct import Construct


def _device(**kwargs):
    return Device(
        name="sonic",
        address="192.0.2.10",
        credential={"username": "admin", "password": "admin"},
        platform="sonic",
        attrs={"source4": "192.0.2.1", "source6": "2001:db8::1"},
        **kwargs,
    )


def _commands(device, kind, target):
    directive = next(d for d in device.directives if d.id.endswith(f"_{kind}__"))
    directive.validate_target(target)
    query = SimpleNamespace(
        device=device, directive=directive, query_type=directive.id, query_target=target
    )
    return Construct(device, query).queries()


@pytest.mark.parametrize(
    "kind,target,expected",
    (
        ("bgp_route", "1.1.1.1", ["vtysh -c 'show bgp ipv4 unicast 1.1.1.1'"]),
        (
            "bgp_aspath",
            "_15169$",
            [
                "vtysh -c 'show bgp ipv4 unicast regexp _15169$'",
                "vtysh -c 'show bgp ipv6 unicast regexp _15169$'",
            ],
        ),
        ("ping", "1.1.1.1", ["ping -4 -c 5 -I 192.0.2.1 1.1.1.1"]),
        ("traceroute", "1.1.1.1", ["traceroute -4 -n -q 1 -w 1 -s 192.0.2.1 1.1.1.1"]),
    ),
)
def test_sonic_uses_frr_commands(kind, target, expected):
    commands = _commands(_device(), kind, target)
    assert [shlex.split(c) for c in commands] == [shlex.split(c) for c in expected]


def test_sonic_quotes_shell_arguments():
    """SONiC runs commands in a shell, so a target must stay one argument."""
    commands = _commands(_device(), "bgp_aspath", "_15169$")
    assert commands[0] == "vtysh -c 'show bgp ipv4 unicast regexp _15169$'"


def test_sonic_vrf_commands():
    commands = _commands(_device(vrf="Vrf-red"), "bgp_route", "1.1.1.0/24")
    assert commands == ["vtysh -c 'show bgp vrf Vrf-red ipv4 unicast 1.1.1.0/24'"]


def test_sonic_device():
    device = _device()
    assert device.get_device_type() == "linux_ssh"
    assert device.structured_output is not True
    assert {d.id for d in device.directives} >= {
        f"__hyperglass_sonic_{kind}__"
        for kind in ("bgp_route", "bgp_aspath", "bgp_community", "ping", "traceroute")
    }
