"""Extreme VOSS platform and directive set (#73)."""

# Standard Library
from types import SimpleNamespace
from unittest.mock import MagicMock

# Third Party
import pytest

# Project
from hyperglass.exceptions.private import InputValidationError
from hyperglass.models.config.devices import Device
from hyperglass.execution.drivers._construct import Construct
from hyperglass.execution.drivers.ssh_netmiko import collect_commands


def _device(**kwargs):
    return Device(
        name="voss",
        address="192.0.2.10",
        credential={"username": "admin", "password": "admin"},
        platform="extreme_vsp",
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
    "vrf,kind,target,expected",
    (
        (None, "bgp_route", "1.1.1.0/24", "show ip bgp route 1.1.1.0/24 community enable"),
        (
            None,
            "bgp_route",
            "2606:4700::/44",
            "show bgp ipv6 route 2606:4700::/44 community enable",
        ),
        (None, "ping", "1.1.1.1", "ping 1.1.1.1 count 5 source 192.0.2.1"),
        (None, "ping", "2606:4700::1111", "ping 2606:4700::1111 count 5 source 2001:db8::1"),
        (None, "traceroute", "1.1.1.1", "traceroute 1.1.1.1 source 192.0.2.1"),
        (
            "CUST-A",
            "bgp_route",
            "1.1.1.0/24",
            "show ip bgp route 1.1.1.0/24 community enable vrf CUST-A",
        ),
        ("CUST-A", "ping", "1.1.1.1", "ping 1.1.1.1 count 5 vrf CUST-A source 192.0.2.1"),
        (
            "CUST-A",
            "traceroute",
            "2606:4700::1111",
            "traceroute 2606:4700::1111 vrf CUST-A source 2001:db8::1",
        ),
    ),
)
def test_voss_commands(vrf, kind, target, expected):
    device = _device(vrf=vrf) if vrf else _device()
    assert _commands(device, kind, target) == [expected]


@pytest.mark.parametrize("target", ("1.1.1.1", "2606:4700::1111"))
def test_voss_route_needs_prefix(target):
    """VOSS matches a host address exactly, so a host target is rejected."""
    with pytest.raises(InputValidationError):
        _commands(_device(), "bgp_route", target)


def test_voss_has_no_pattern_queries():
    device = _device()
    assert device.get_device_type() == "extreme_vsp"
    assert {d.id for d in device.directives} == {
        f"__hyperglass_extreme_vsp_{kind}__" for kind in ("bgp_route", "ping", "traceroute")
    }


def test_voss_enters_privileged_mode():
    """VOSS rejects traceroute outside privileged mode."""
    connection = MagicMock()
    connection.send_command.return_value = "ok"
    collect_commands(connection, "extreme_vsp", ["traceroute 1.1.1.1"], 30)
    connection.enable.assert_called_once()
