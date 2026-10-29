"""Version-filtered and on-error fallback commands (#109)."""

# Standard Library
from unittest.mock import Mock

# Third Party
import pytest
from pydantic import ValidationError

# Project
from hyperglass.state import use_state
from hyperglass.state.hooks import _use_state
from hyperglass.models.api import Query
from hyperglass.configuration import init_ui_params
from hyperglass.models.directive import RuleWithIPv6, version_matches
from hyperglass.models.config.params import Params
from hyperglass.models.config.devices import Devices
from hyperglass.defaults.directives import init_builtin_directives

# Local
from .. import ssh_netmiko
from .._construct import Construct

FULL = "traceroute ipv6 2606:4700::1111 timeout 1 probe 2 source 2001:db8::1"
BARE = "traceroute ipv6 2606:4700::1111"


def _device(name, os_version):
    device = {
        "name": name,
        "address": "127.0.0.1",
        "credential": {"username": "lg", "password": "lg"},
        "platform": "cisco_ios",
        "attrs": {"source4": "192.0.2.1", "source6": "2001:db8::1"},
    }
    if os_version is not None:
        device["os_version"] = os_version
    return device


@pytest.fixture
def state():
    _use_state.cache_clear()
    _state = use_state()
    params = Params()
    _state.cache.set("params", params)
    _state.cache.set("directives", init_builtin_directives())
    devices = Devices(
        _device("ios15", "15.9(3)M6"),
        _device("iosxe", "17.18.02"),
        _device("unknown", None),
        _device("number", 15.9),
    )
    _state.cache.set("devices", devices)
    _state.cache.set("ui_params", init_ui_params(params=params, devices=devices))
    yield _state
    _state.clear()


def _construct(state, location):
    query = Query(
        queryLocation=location,
        queryTarget="2606:4700::1111",
        queryType="__hyperglass_cisco_ios_traceroute__",
    )
    construct = Construct(device=state.devices[location], query=query)
    return construct.queries(), construct.fallbacks


@pytest.mark.parametrize(
    ("version", "spec", "matches"),
    [
        ("15.9(3)M6", "<16", True),
        ("12.4(24)T", "<16", True),
        ("16.12.4", "<16", False),
        ("17.18.02", "<16", False),
        ("15.9", ">=15,<16", True),
        ("15.9", "==15", True),
        ("15.9", "==15.8", False),
        (None, "<16", False),
        ("", "<16", False),
    ],
)
def test_version_matches(version, spec, matches):
    assert version_matches(version, spec) is matches


@pytest.mark.parametrize("spec", ["16", "<sixteen", "<16,", "~=16"])
def test_invalid_version_filter_is_rejected(spec):
    with pytest.raises(ValidationError):
        RuleWithIPv6(condition="::/0", command="x", fallback_command="y", fallback_os_version=spec)


def test_version_filter_needs_fallback_commands():
    with pytest.raises(ValidationError):
        RuleWithIPv6(condition="::/0", command="x", fallback_os_version="<16")


@pytest.mark.parametrize("location", ["ios15", "number"])
def test_matching_version_runs_fallback_directly(state, location):
    assert _construct(state, location) == ([BARE], [None])


@pytest.mark.parametrize("location", ["iosxe", "unknown"])
def test_other_versions_run_full_command_with_fallback(state, location):
    assert _construct(state, location) == ([FULL], [BARE])


def test_rejected_command_runs_fallback(monkeypatch):
    log = Mock()
    monkeypatch.setattr(ssh_netmiko, "log", log)
    session = Mock()
    session.send_command.side_effect = [
        "% Invalid input detected at '^' marker.",
        "1 2606:4700::1111",
    ]
    result = ssh_netmiko.collect_commands(
        session, "cisco_ios", [FULL], 90, fallbacks=[BARE], device="lab-iosv"
    )
    assert result == ("1 2606:4700::1111",)
    assert [call.args[0] for call in session.send_command.call_args_list] == [FULL, BARE]
    log.bind.assert_called_once_with(device="lab-iosv", command=FULL, fallback=BARE)
    log.bind.return_value.warning.assert_called_once()


def test_accepted_command_skips_fallback(monkeypatch):
    log = Mock()
    monkeypatch.setattr(ssh_netmiko, "log", log)
    session = Mock()
    session.send_command.return_value = "1 2606:4700::1111"
    result = ssh_netmiko.collect_commands(
        session, "cisco_ios", [FULL], 90, fallbacks=[BARE], device="lab-iol"
    )
    assert result == ("1 2606:4700::1111",)
    session.send_command.assert_called_once()
    log.bind.assert_not_called()
