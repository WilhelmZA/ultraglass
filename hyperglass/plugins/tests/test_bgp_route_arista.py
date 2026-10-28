"""Arista BGP Route Parsing Tests."""

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
from .._builtin.bgp_route_arista import BGPRoutePluginArista
from .._builtin.bgp_route_arista import parse_arista

DEPENDS_KWARGS = {
    "depends": [
        "hyperglass/models/tests/test_util.py::test_check_legacy_fields",
        "hyperglass/external/tests/test_rpki.py::test_rpki",
    ],
    "scope": "session",
}

SAMPLE = Path(__file__).parent.parent.parent.parent / ".samples" / "arista_route.json"


def _tester(sample: str):
    plugin = BGPRoutePluginArista()

    device = MockDevice(
        name="Test Device",
        address="127.0.0.1",
        group="Test Network",
        credential={"username": "", "password": ""},
        platform="arista",
        structured_output=True,
        directives=["__hyperglass_arista_eos_bgp_route_table__"],
        attrs={"source4": "192.0.2.1", "source6": "2001:db8::1"},
    )

    query = type("Query", (), {"device": device})

    result = plugin.process(output=(sample,), query=query)
    assert isinstance(result, BGPRouteTable), "Invalid parsed result"
    assert hasattr(result, "count"), "BGP Table missing count"
    assert result.count > 0, "BGP Table count is 0"


@pytest.mark.dependency(**DEPENDS_KWARGS)
def test_arista_route_sample():
    with SAMPLE.open("r") as file:
        sample = file.read()
    return _tester(sample)


def test_captured_aspath_without_route_detail():
    sample = (Path(__file__).parent / "fixtures" / "arista_aspath.json").read_text()
    result = parse_arista((sample,))
    assert result.count == 1
    assert result.routes[0].as_path == [65000, 37239, 13335]
    assert result.routes[0].communities == []


def test_arista_merges_multiple_json_responses():
    # The second document represents an empty address family.
    sample = (Path(__file__).parent / "fixtures" / "arista_aspath.json").read_text()
    empty = '{"vrfs":{"default":{"vrf":"default","routerId":"10.250.7.1","asn":"65007","bgpRouteEntries":{}}}}'
    result = parse_arista((sample, empty))
    assert result.count == 1
    assert len(result.routes) == 1


def test_asdot_as_path_keeps_origin():
    sample = SAMPLE.read_text().replace('"65002 65003"', '"65000 65000.100"')
    sample = sample.replace('"asn": "65001"', '"asn": "0.65001"')
    result = parse_arista((sample,))

    assert result.routes[0].as_path == [65000, 4259840100]


def test_captured_large_community():
    sample = (Path(__file__).parent / "fixtures" / "arista_large_community.json").read_text()
    result = parse_arista((sample,))

    assert result.routes[0].communities == ["65000:100", "65000:1:1"]


def test_captured_vrf_local_route():
    sample = (Path(__file__).parent / "fixtures" / "arista_vrf_local_route.json").read_text()
    result = parse_arista((sample,))

    assert result.vrf == "LAB"
    assert result.routes[0].prefix == "198.51.100.0/24"
    assert result.routes[0].local_preference == 100
    # A locally originated route has an empty AS path; the source AS is the local AS.
    assert result.routes[0].as_path == []
    assert result.routes[0].source_as == 65007
