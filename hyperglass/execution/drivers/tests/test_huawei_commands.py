"""Huawei VRP 8.180 command forms and command errors (#155)."""

# Standard Library
from unittest.mock import Mock

# Third Party
import pytest

# Project
from hyperglass.state import use_state
from hyperglass.plugins import InputPluginManager
from hyperglass.state.hooks import _use_state
from hyperglass.models.api import Query
from hyperglass.configuration import init_ui_params
from hyperglass.plugins._builtin import BGPRoutePluginHuawei
from hyperglass.defaults.directives import init_builtin_directives
from hyperglass.models.config.params import Params
from hyperglass.models.config.devices import Devices

# Local
from .. import ssh_netmiko
from .._common import command_error
from .._construct import Construct

TRACE = "__hyperglass_huawei_traceroute__"
PING = "__hyperglass_huawei_ping__"

# Device responses captured from the lab nodes on 30 October 2026.
CE12800_TOO_MANY = (
    "                                         ^\nError: Too many parameters found at '^' position."
)
NE40E_TOO_MANY = "Error[4]: Too many parameters found at '^' position."
CE12800_TRACE6 = "  traceroute to FD00:250:8::  30 hops max,60 bytes packet\n 1 FD00:250:8:: 1 ms"


@pytest.fixture(params=["huawei", "huawei_vrpv8"])
def huawei_state(request):
    """One default-table and one VRF Huawei device per platform key."""
    _use_state.cache_clear()
    state = use_state()
    params = Params()
    state.cache.set("params", params)
    state.cache.set("directives", init_builtin_directives())
    InputPluginManager().register(BGPRoutePluginHuawei)
    base = {
        "address": "127.0.0.1",
        "credential": {"username": "", "password": ""},
        "platform": request.param,
    }
    devices = Devices(
        {**base, "name": "default", "attrs": {"source4": "10.250.8.1", "source6": "fd00:250:8::1"}},
        {
            **base,
            "name": "vrf",
            "vrf": "LAB",
            "attrs": {"source4": "192.0.2.108", "source6": "2001:db8:100::8"},
        },
    )
    state.cache.set("devices", devices)
    state.cache.set("ui_params", init_ui_params(params=params, devices=devices))
    yield state
    state.clear()


def construct(state, location, query_type, target):
    query = Query(queryLocation=location, queryTarget=target, queryType=query_type)
    return Construct(device=state.devices[location], query=query)


def test_ipv6_traceroute_keeps_source_and_falls_back_without_it(huawei_state):
    """The NE40E accepts `-a`; the CE12800 rejects it and runs the fallback."""
    constructor = construct(huawei_state, "default", TRACE, "2606:4700:4700::1111")
    assert constructor.queries() == [
        "tracert ipv6 -w 500 -q 1 -f 1 -a fd00:250:8::1 2606:4700:4700::1111"
    ]
    assert constructor.fallbacks == ["tracert ipv6 -w 500 -q 1 -f 1 2606:4700:4700::1111"]


def test_ipv4_traceroute_has_no_fallback(huawei_state):
    constructor = construct(huawei_state, "default", TRACE, "1.1.1.1")
    assert constructor.queries() == ["tracert -w 500 -q 1 -f 1 -a 10.250.8.1 1.1.1.1"]
    assert constructor.fallbacks == [None]


@pytest.mark.parametrize(
    "query_type,target,expected",
    [
        (PING, "2001:db8:100::8", "ping ipv6 -c 5 vpn-instance LAB 2001:db8:100::8"),
        (
            TRACE,
            "2001:db8:100::8",
            "tracert ipv6 -w 500 -q 1 -f 1 vpn-instance LAB 2001:db8:100::8",
        ),
        (PING, "192.0.2.108", "ping -c 5 -vpn-instance LAB 192.0.2.108"),
        (TRACE, "192.0.2.108", "tracert -w 500 -q 1 -f 1 -vpn-instance LAB 192.0.2.108"),
    ],
)
def test_vrf_ping_and_traceroute_forms(huawei_state, query_type, target, expected):
    """VRP 8.180 takes `vpn-instance` without a dash on the IPv6 forms only."""
    assert construct(huawei_state, "vrf", query_type, target).queries() == [expected]


@pytest.mark.parametrize("output", [CE12800_TOO_MANY, NE40E_TOO_MANY])
def test_huawei_parameter_errors_are_command_errors(output):
    """These used to return `success`, as text or as an empty hop table."""
    assert command_error((output,))


def test_huawei_traceroute_output_is_not_a_command_error():
    assert not command_error((CE12800_TRACE6,))


def test_rejected_ipv6_traceroute_runs_the_fallback():
    session = Mock()
    session.send_command.side_effect = [CE12800_TOO_MANY, CE12800_TRACE6]
    primary = "tracert ipv6 -w 500 -q 1 -f 1 -a fd00:250:8::1 fd00:250:8::"
    fallback = "tracert ipv6 -w 500 -q 1 -f 1 fd00:250:8::"
    responses = ssh_netmiko.collect_commands(
        session, "huawei_vrpv8", [primary], 300, fallbacks=[fallback]
    )
    assert responses == (CE12800_TRACE6,)
    assert [call.args[0] for call in session.send_command.call_args_list] == [primary, fallback]
