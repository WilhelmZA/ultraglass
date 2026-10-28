"""VyOS BGP route parsing tests, using FRR JSON captured from the lab VyOS router."""

# Standard Library
from pathlib import Path

# Third Party
import pytest

# Project
from hyperglass.models.data.bgp_route import BGPRouteTable

# Local
from ._fixtures import MockDevice
from .._builtin.bgp_route_frr import BGPRoutePluginFrr

FIXTURES = Path(__file__).parent / "fixtures" / "vyos-live"


def _process(name: str, directive: str):
    device = MockDevice(
        name="lab-vyos",
        address="127.0.0.1",
        group="Test Network",
        credential={"username": "", "password": ""},
        platform="vyos",
        structured_output=True,
        attrs={"source4": "192.0.2.1", "source6": "2001:db8::1"},
    )
    query = type("Query", (), {"device": device, "directive": type("D", (), {"id": directive})})
    return BGPRoutePluginFrr().process(output=((FIXTURES / name).read_text(),), query=query)


@pytest.mark.parametrize("name", ("route4.json", "route6.json"))
def test_vyos_route_detail(name):
    result = _process(name, "__hyperglass_vyos_bgp_route_table__")

    assert isinstance(result, BGPRouteTable)
    assert result.count > 1
    assert all(route.as_path for route in result.routes)
    assert any(route.communities for route in result.routes)
    assert sum(route.active for route in result.routes) == 1


@pytest.mark.parametrize(
    "name,directive",
    (
        ("aspath4.json", "__hyperglass_vyos_bgp_aspath_table__"),
        ("community4.json", "__hyperglass_vyos_bgp_community_table__"),
    ),
)
def test_vyos_route_summary(name, directive):
    result = _process(name, directive)

    assert result.count == 5 if name == "aspath4.json" else result.count == 30
    assert len({route.prefix for route in result.routes}) == 5
    assert all(route.as_path[-1] == 13335 for route in result.routes)
    # Summary output carries no communities or update time.
    assert all(route.communities == [] and route.age == 0 for route in result.routes)
