"""Extreme EXOS platform and directive set (#73)."""

# Standard Library
from types import SimpleNamespace

# Third Party
import pytest

# Project
from hyperglass.exceptions.public import InputInvalid
from hyperglass.exceptions.private import InputValidationError
from hyperglass.models.config.devices import Device
from hyperglass.execution.drivers._construct import Construct


def _device(**kwargs):
    return Device(
        name="exos",
        address="192.0.2.10",
        credential={"username": "admin", "password": "admin"},
        platform="extreme_exos",
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
        (
            "bgp_route",
            "1.1.1.0/24",
            ["show bgp routes detail ipv4-unicast network 1.1.1.0/24 exact"],
        ),
        (
            "bgp_route",
            "2606:4700::/44",
            ["show bgp routes detail ipv6-unicast network 2606:4700::/44 exact"],
        ),
        (
            "bgp_aspath",
            "_15169$",
            [
                'show bgp routes detail ipv4-unicast as-path "_15169$"',
                'show bgp routes detail ipv6-unicast as-path "_15169$"',
            ],
        ),
        (
            "bgp_community",
            "15169:1",
            [
                "show bgp routes detail ipv4-unicast community 15169 : 1",
                "show bgp routes detail ipv6-unicast community 15169 : 1",
            ],
        ),
        ("ping", "1.1.1.1", ["ping count 5 1.1.1.1 from 192.0.2.1"]),
        ("ping", "2606:4700::1111", ["ping count 5 ipv6 2606:4700::1111 from 2001:db8::1"]),
        ("traceroute", "1.1.1.1", ["traceroute 1.1.1.1 from 192.0.2.1"]),
        (
            "traceroute",
            "2606:4700::1111",
            ["traceroute ipv6 2606:4700::1111 from 2001:db8::1"],
        ),
    ),
)
def test_exos_commands(kind, target, expected):
    assert _commands(_device(), kind, target) == expected


@pytest.mark.parametrize(
    "kind,target,expected",
    (
        (
            "bgp_route",
            "1.1.1.0/24",
            ["show bgp routes detail ipv4-unicast network 1.1.1.0/24 exact vr CUST-A"],
        ),
        (
            "bgp_community",
            "15169:1",
            [
                "show bgp routes detail ipv4-unicast community 15169 : 1 vr CUST-A",
                "show bgp routes detail ipv6-unicast community 15169 : 1 vr CUST-A",
            ],
        ),
        ("ping", "1.1.1.1", ["ping vr CUST-A count 5 1.1.1.1 from 192.0.2.1"]),
        (
            "traceroute",
            "2606:4700::1111",
            ["traceroute vr CUST-A ipv6 2606:4700::1111 from 2001:db8::1"],
        ),
    ),
)
def test_exos_vrf_commands(kind, target, expected):
    assert _commands(_device(vrf="CUST-A"), kind, target) == expected


@pytest.mark.parametrize("target", ("1.1.1.1", "2606:4700::1111"))
def test_exos_route_needs_prefix(target):
    """EXOS has no longest-match lookup, so a host address is rejected."""
    with pytest.raises(InputValidationError):
        _commands(_device(), "bgp_route", target)


def test_exos_rejects_large_community():
    with pytest.raises(InputInvalid):
        _commands(_device(), "bgp_community", "4200000001:1:2")


def test_exos_uses_netmiko_exos_driver():
    device = _device()
    assert device.get_device_type() == "extreme_exos"
    assert {d.id for d in device.directives} >= {
        f"__hyperglass_extreme_exos_{kind}__"
        for kind in ("bgp_route", "bgp_aspath", "bgp_community", "ping", "traceroute")
    }
