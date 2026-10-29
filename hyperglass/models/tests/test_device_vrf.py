"""Native VRF support for built-in directives (#50)."""

# Standard Library
from types import SimpleNamespace

# Third Party
import pytest
from pydantic import ValidationError

# Project
from hyperglass.exceptions.private import ConfigError
from hyperglass.models.directive import Directive
from hyperglass.models.config.devices import Device, directive_attr_keys
from hyperglass.execution.drivers._construct import Construct

ATTRS = {"source4": "192.0.2.1", "source6": "2001:db8::1"}


def _device(platform, **kwargs):
    return Device(
        name="lab",
        address="192.0.2.10",
        credential={"username": "lg", "password": "lg"},
        platform=platform,
        attrs=ATTRS,
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
    "platform,kind,target,expected",
    (
        ("arista_eos", "bgp_route_table", "1.1.1.1", "show ip bgp 1.1.1.1 vrf LAB | json"),
        ("arista_eos", "ping", "1.1.1.1", "ping vrf LAB ip 1.1.1.1"),
        (
            "frr",
            "bgp_route_table",
            "1.1.1.1",
            "vtysh -c 'show bgp vrf LAB ipv4 unicast 1.1.1.1 json'",
        ),
        (
            "vyos",
            "bgp_route_table",
            "1.1.1.1",
            "vtysh -c 'show bgp vrf LAB ipv4 unicast 1.1.1.1 json'",
        ),
        ("vyos", "traceroute", "1.1.1.1", "traceroute 1.1.1.1 vrf LAB icmp"),
        (
            "huawei",
            "bgp_route_table",
            "1.1.1.1",
            "display bgp vpnv4 vpn-instance LAB routing-table 1.1.1.1 | no-more",
        ),
        ("huawei", "ping", "1.1.1.1", "ping -c 5 -vpn-instance LAB 1.1.1.1"),
        ("mikrotik_routeros", "ping", "1.1.1.1", "ping vrf=LAB count=5 1.1.1.1"),
    ),
)
def test_vrf_commands(platform, kind, target, expected):
    device = _device(platform, vrf="LAB", structured_output=kind.endswith("_table"))
    assert _commands(device, kind, target)[0] == expected


def test_default_commands_unchanged():
    assert _commands(_device("arista_eos"), "ping", "1.1.1.1") == [
        "ping ip 1.1.1.1 source 192.0.2.1"
    ]


def test_vrf_drops_builtins_without_vrf_form():
    kinds = {d.id for d in _device("frr", vrf="LAB").directives}
    assert "__hyperglass_frr_bgp_route_table__" in kinds
    assert "__hyperglass_frr_ping__" not in kinds
    assert "__hyperglass_frr_ping__" in {d.id for d in _device("frr").directives}


def test_vrf_unsupported_platform():
    with pytest.raises(ConfigError, match="no VRF-capable"):
        _device("bird", vrf="LAB")


@pytest.mark.parametrize("vrf", ("LAB; id", "a b", "x" * 65, ""))
def test_vrf_name_is_validated(vrf):
    with pytest.raises(ValidationError):
        _device("arista_eos", vrf=vrf)


def test_vrf_device_needs_no_attrs_for_unused_commands():
    """FRR VRF commands reference no attribute, so no source address is required (#95)."""
    device = Device(
        name="lab",
        address="192.0.2.10",
        credential={"username": "lg", "password": "lg"},
        platform="frr",
        vrf="LAB",
    )
    assert device.vrf == "LAB"


def test_default_device_still_needs_attrs():
    with pytest.raises((ConfigError, ValidationError), match="source[46]"):
        Device(
            name="lab",
            address="192.0.2.10",
            credential={"username": "lg", "password": "lg"},
            platform="frr",
        )


def test_attr_keys_follow_the_commands_the_device_runs():
    """VRF devices count VRF commands, where a rule has them (#95)."""
    directive = Directive(
        id="lab-ping",
        name="Ping",
        rules=[
            {
                "condition": "0.0.0.0/0",
                "command": "ping {target} source {source4}",
                "vrf_command": "ping vrf {vrf} {target} source {loopback}",
            },
            {"condition": "::/0", "command": "ping {target} source {source6}"},
        ],
        field={"description": "IP Address"},
    )
    assert directive_attr_keys([directive], vrf=False) == {"source4", "source6"}
    # The IPv6 rule has no VRF form, so a VRF device would run its default command.
    assert directive_attr_keys([directive], vrf=True) == {"loopback", "source6"}
