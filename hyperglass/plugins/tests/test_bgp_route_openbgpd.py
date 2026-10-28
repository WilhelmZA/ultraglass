"""OpenBGPD BGP route parsing tests, using JSON captured from the lab OpenBGPD router."""

# Standard Library
from pathlib import Path

# Third Party
import pytest

# Project
from hyperglass.models.data.bgp_route import BGPRouteTable

# Local
from ._fixtures import MockDevice
from .._builtin.bgp_route_openbgpd import BGPRoutePluginOpenBGPD

FIXTURES = Path(__file__).parent / "fixtures" / "openbgpd-live"


def _process(name: str):
    device = MockDevice(
        name="lab-openbgpd",
        address="127.0.0.1",
        group="Test Network",
        credential={"username": "", "password": ""},
        platform="openbgpd",
        structured_output=True,
        attrs={"source4": "192.0.2.1", "source6": "2001:db8::1"},
    )
    query = type("Query", (), {"device": device})
    return BGPRoutePluginOpenBGPD().process(output=((FIXTURES / name).read_text(),), query=query)


@pytest.mark.parametrize("name,count", (("route4.json", 13), ("route6.json", 11)))
def test_openbgpd_route(name, count):
    result = _process(name)

    assert isinstance(result, BGPRouteTable)
    assert result.count == count
    assert sum(route.active for route in result.routes) == 1
    assert all(route.as_path[0] == 65000 for route in result.routes)
    assert any(route.communities for route in result.routes)
    # The lab router does not validate RPKI, so every path is not-found.
    assert {route.rpki_state for route in result.routes} == {2}


@pytest.mark.parametrize("name", ("aspath4.json", "community4.json"))
def test_openbgpd_filtered_rib(name):
    result = _process(name)

    assert result.count == 5
    if name == "aspath4.json":
        assert all(route.as_path[-1] == 13335 for route in result.routes)
    else:
        assert all("37195:302" in route.communities for route in result.routes)


def test_openbgpd_large_community():
    result = _process("large_community.json")

    assert result.routes[0].communities == ["65000:100", "65000:1:1"]


def test_openbgpd_empty_result():
    assert _process("empty.json") is None
