"""TNSR platform loading and built-in commands (#102)."""

# Standard Library
from types import SimpleNamespace

# Third Party
import pytest

# Project
from hyperglass.models.config.devices import Device
from hyperglass.execution.drivers._construct import Construct


def _device(**overrides):
    config = {
        "name": "tnsr",
        "address": "192.0.2.10",
        "credential": {"username": "tnsr", "password": "tnsr"},
        "platform": "tnsr",
        "attrs": {"source4": "192.0.2.1", "source6": "2001:db8::1"},
    }
    config.update(overrides)
    return Device(**config)


def _commands(device, kind, target):
    directive = next(d for d in device.directives if d.id.endswith(f"_{kind}__"))
    directive.validate_target(target)
    query = SimpleNamespace(
        device=device, directive=directive, query_type=directive.id, query_target=target
    )
    return Construct(device, query).queries()


def test_tnsr_uses_generic_ssh_without_paging():
    device = _device()
    assert device.platform == "tnsr"
    assert device.get_device_type() == "generic"
    assert device.disable_paging is False
    assert {d.id for d in device.directives} == {
        f"__hyperglass_tnsr_{kind}__"
        for kind in ("bgp_route", "bgp_aspath", "bgp_community", "ping", "traceroute")
    }


def test_tnsr_alias_and_explicit_paging():
    assert _device(platform="tsnr").platform == "tnsr"
    assert _device(disable_paging=True).disable_paging is True


@pytest.mark.parametrize(
    "kind,target,expected",
    (
        (
            "bgp_route",
            "1.1.1.1",
            ['dataplane shell sudo vtysh -c "show bgp ipv4 unicast 1.1.1.1"'],
        ),
        (
            "bgp_route",
            "2606:4700::1111",
            ['dataplane shell sudo vtysh -c "show bgp ipv6 unicast 2606:4700::1111"'],
        ),
        (
            "bgp_aspath",
            "_13335$",
            [
                'dataplane shell sudo vtysh -c "show bgp ipv4 unicast regexp _13335$"',
                'dataplane shell sudo vtysh -c "show bgp ipv6 unicast regexp _13335$"',
            ],
        ),
        (
            "bgp_community",
            "65000:777",
            [
                'dataplane shell sudo vtysh -c "show bgp ipv4 unicast community 65000:777"',
                'dataplane shell sudo vtysh -c "show bgp ipv6 unicast community 65000:777"',
            ],
        ),
        (
            "ping",
            "1.1.1.1",
            ["ping 1.1.1.1 ipv4 source 192.0.2.1 count 5 timeout 1"],
        ),
        (
            "traceroute",
            "1.1.1.1",
            ["traceroute 1.1.1.1 ipv4 source 192.0.2.1 timeout 1 waittime 1"],
        ),
    ),
)
def test_tnsr_commands(kind, target, expected):
    assert _commands(_device(), kind, target) == expected
