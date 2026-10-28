"""VyOS 1.3 platform and directive set (#51)."""

# Standard Library
import shlex
from types import SimpleNamespace

# Third Party
import pytest

# Project
from hyperglass.models.config.devices import Device
from hyperglass.execution.drivers._construct import Construct


def _device(platform):
    return Device(
        name="vyos",
        address="192.0.2.10",
        credential={"username": "vyos", "password": "vyos"},
        platform=platform,
        attrs={"source4": "192.0.2.1", "source6": "2001:db8::1"},
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
        ("bgp_route", "1.1.1.1", ["show ip bgp 1.1.1.1"]),
        ("bgp_route", "2606:4700::1111", ["show ipv6 bgp 2606:4700::1111"]),
        ("bgp_aspath", "_13335$", ["show ip bgp regexp _13335$", "show ipv6 bgp regexp _13335$"]),
        (
            "bgp_community",
            "13335:10045",
            ["show ip bgp community 13335:10045", "show ipv6 bgp community 13335:10045"],
        ),
        ("ping", "1.1.1.1", ["ping 1.1.1.1 count 5 interface 192.0.2.1"]),
        ("traceroute", "1.1.1.1", ["traceroute 1.1.1.1"]),
    ),
)
def test_vyos_1_3_commands(kind, target, expected):
    commands = _commands(_device("vyos_1_3"), kind, target)
    assert [shlex.split(c) for c in commands] == [shlex.split(c) for c in expected]


def test_vyos_1_3_uses_vyos_driver():
    device = _device("vyos_1_3")
    assert device.get_device_type() == "vyos"
    assert {d.id for d in device.directives} == {
        f"__hyperglass_vyos_1_3_{kind}__"
        for kind in ("bgp_route", "bgp_aspath", "bgp_community", "ping", "traceroute")
    }


def test_vyos_keeps_current_syntax():
    assert _commands(_device("vyos"), "traceroute", "1.1.1.1") == [
        "traceroute 1.1.1.1 source-address 192.0.2.1 icmp"
    ]
