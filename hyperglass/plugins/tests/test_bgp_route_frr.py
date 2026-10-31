"""FRR BGP Route Parsing Tests."""

# flake8: noqa
# Standard Library
from pathlib import Path

# Third Party
import pytest

# Project
from hyperglass.models.config.devices import Device
from hyperglass.models.data.bgp_route import BGPRouteTable

# Local
from ._fixtures import MockDevice
from .._builtin.bgp_route_frr import BGPRoutePluginFrr

DEPENDS_KWARGS = {
    "depends": [
        "hyperglass/models/tests/test_util.py::test_check_legacy_fields",
        "hyperglass/external/tests/test_rpki.py::test_rpki",
    ],
    "scope": "session",
}

SAMPLE = Path(__file__).parent.parent.parent.parent / ".samples" / "frr_bgp_route.json"


def _tester(sample: str):
    plugin = BGPRoutePluginFrr()

    device = MockDevice(
        name="Test Device",
        address="127.0.0.1",
        group="Test Network",
        credential={"username": "", "password": ""},
        platform="frr",
        structured_output=True,
        directives=["__hyperglass_frr_bgp_route_table__"],
        attrs={"source4": "192.0.2.1", "source6": "2001:db8::1"},
    )

    query = type("Query", (), {"device": device})

    result = plugin.process(output=(sample,), query=query)
    assert isinstance(result, BGPRouteTable), "Invalid parsed result"
    assert hasattr(result, "count"), "BGP Table missing count"
    assert result.count > 0, "BGP Table count is 0"


@pytest.mark.dependency(**DEPENDS_KWARGS)
def test_frr_route_sample():
    with SAMPLE.open("r") as file:
        sample = file.read()
    return _tester(sample)


FIXTURES = Path(__file__).parent / "fixtures"


def _process(sample: str):
    plugin = BGPRoutePluginFrr()
    device = MockDevice(
        name="Test Device",
        address="127.0.0.1",
        group="Test Network",
        credential={"username": "", "password": ""},
        platform="frr",
        structured_output=True,
        directives=["__hyperglass_frr_bgp_route_table__"],
        attrs={"source4": "192.0.2.1", "source6": "2001:db8::1"},
    )
    query = type("Query", (), {"device": device})
    return plugin.process(output=(sample,), query=query)


def test_frr_route_not_in_table_is_empty():
    assert _process((FIXTURES / "frr_route_empty.json").read_text()) is None


def test_frr_local_prefix_has_empty_as_path():
    result = _process((FIXTURES / "frr_route_local.json").read_text())

    assert result.count == 1
    assert result.routes[0].as_path == []


def test_frr_inaccessible_next_hop_without_metric():
    result = _process((FIXTURES / "frr_route_inaccessible_nexthop.json").read_text())

    assert result.count == 1
    assert result.routes[0].next_hop == "10.99.99.99"


def _process_vrf(outputs, platform: str = "frr", vrf: str = "LAB"):
    plugin = BGPRoutePluginFrr()
    device = MockDevice(
        name="Test Device",
        address="127.0.0.1",
        group="Test Network",
        credential={"username": "", "password": ""},
        platform=platform,
        structured_output=True,
        vrf=vrf,
        directives=[f"__hyperglass_{platform}_bgp_route_table__"],
        attrs={"source4": "192.0.2.1", "source6": "2001:db8::1"},
    )
    query = type("Query", (), {"device": device})
    return plugin.process(output=tuple(outputs), query=query)


@pytest.mark.parametrize("platform", ("frr", "vyos", "sonic", "cumulus_linux"))
def test_frr_vrf_route_uses_device_vrf(platform):
    # `show bgp vrf LAB ipv4 unicast <prefix> json` carries no VRF name (#134).
    result = _process_vrf([(FIXTURES / "frr_vrf_route.json").read_text()], platform=platform)

    assert result.count == 1
    assert result.vrf == "LAB"


@pytest.mark.parametrize("platform", ("frr", "vyos", "sonic", "cumulus_linux"))
def test_frr_vrf_aspath_uses_vrf_name_from_output(platform):
    # Regexp and community output carries `vrfName`, which wins over the device setting.
    outputs = [(FIXTURES / f"frr_vrf_aspath{family}.json").read_text() for family in (4, 6)]
    result = _process_vrf(outputs, platform=platform, vrf="CONFIGURED")

    assert result.count == 2
    assert result.vrf == "LAB"


def test_frr_route_without_vrf_is_default():
    result = _process((FIXTURES / "frr_route_local.json").read_text())

    assert result.vrf == "default"
