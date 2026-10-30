"""The lab Huawei VRF location builds vpn-instance commands (#130)."""

# Standard Library
from pathlib import Path

# Third Party
import yaml
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
from .._construct import Construct

LAB = Path(__file__).parents[4] / "lab" / "configs"


@pytest.fixture(params=["ultraglass", "ultraglass-text"])
def lab_state(request):
    """Load the lab-huawei-vrpv8-vrf entry exactly as the lab device file defines it."""
    entries = yaml.safe_load((LAB / request.param / "devices.yaml").read_text())["devices"]
    (entry,) = (e for e in entries if e["name"] == "lab-huawei-vrpv8-vrf")
    _use_state.cache_clear()
    state = use_state()
    params = Params()
    state.cache.set("params", params)
    state.cache.set("directives", init_builtin_directives())
    InputPluginManager().register(BGPRoutePluginHuawei)
    devices = Devices(entry)
    state.cache.set("devices", devices)
    state.cache.set("ui_params", init_ui_params(params=params, devices=devices))
    yield state
    state.clear()


def commands(state, name, target):
    device = state.devices["lab-huawei-vrpv8-vrf"]
    directive = next(d for d in device.directives if d.name == name)
    query = Query(queryLocation=device.name, queryTarget=target, queryType=directive.id)
    return Construct(device=device, query=query).queries()


def test_lab_huawei_vrf_offers_all_query_types(lab_state):
    device = lab_state.devices["lab-huawei-vrpv8-vrf"]
    assert device.vrf == "LAB"
    assert {d.name for d in device.directives} == {
        "BGP Route",
        "BGP AS Path",
        "BGP Community",
        "Ping",
        "Traceroute",
    }


@pytest.mark.parametrize(
    "name,target,expected",
    [
        ("BGP Route", "198.51.100.0/24", "vpnv4 vpn-instance LAB routing-table 198.51.100.0 24"),
        (
            "BGP Route",
            "2001:db8:100::/48",
            "vpnv6 vpn-instance LAB routing-table 2001:db8:100:: 48",
        ),
        ("BGP AS Path", "_65008$", "vpnv4 vpn-instance LAB routing-table regular-expression"),
        ("BGP Community", "65000:777", "vpnv4 vpn-instance LAB routing-table community"),
        ("Ping", "198.51.100.1", "ping -c 5 -vpn-instance LAB 198.51.100.1"),
        ("Traceroute", "2001:db8:100::1", "-vpn-instance LAB 2001:db8:100::1"),
    ],
)
def test_lab_huawei_vrf_commands(lab_state, name, target, expected):
    assert any(expected in command for command in commands(lab_state, name, target))
