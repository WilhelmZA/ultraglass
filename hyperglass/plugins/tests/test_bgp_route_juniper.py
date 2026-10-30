"""Juniper BGP Route Parsing Tests."""

# flake8: noqa
# Standard Library
from pathlib import Path
from unittest.mock import patch

# Third Party
import pytest

# Project
from hyperglass.exceptions.private import ParsingError
from hyperglass.models.data.bgp_route import BGPRouteTable

# Local
from ._fixtures import MockDevice
from .._builtin.bgp_route_juniper import BGPRoutePluginJuniper, parse_juniper

DEPENDS_KWARGS = {
    "depends": [
        "hyperglass/models/tests/test_util.py::test_check_legacy_fields",
        "hyperglass/external/tests/test_rpki.py::test_rpki",
    ],
    "scope": "session",
}

DIRECT = Path(__file__).parent.parent.parent.parent / ".samples" / "juniper_route_direct.xml"
INDIRECT = Path(__file__).parent.parent.parent.parent / ".samples" / "juniper_route_indirect.xml"
AS_PATH = Path(__file__).parent.parent.parent.parent / ".samples" / "juniper_route_aspath.xml"


def _parse(sample: str):
    plugin = BGPRoutePluginJuniper()

    device = MockDevice(
        name="Test Device",
        address="127.0.0.1",
        group="Test Network",
        credential={"username": "", "password": ""},
        platform="juniper",
        structured_output=True,
        directives=[],
        attrs={"source4": "192.0.2.1", "source6": "2001:db8::1"},
    )

    query = type("Query", (), {"device": device})

    return plugin.process(output=(sample,), query=query)


def _tester(sample: str):
    plugin = BGPRoutePluginJuniper()

    device = MockDevice(
        name="Test Device",
        address="127.0.0.1",
        group="Test Network",
        credential={"username": "", "password": ""},
        platform="juniper",
        structured_output=True,
        directives=[],
        attrs={"source4": "192.0.2.1", "source6": "2001:db8::1"},
    )

    query = type("Query", (), {"device": device})

    result = plugin.process(output=(sample,), query=query)
    assert isinstance(result, BGPRouteTable), "Invalid parsed result"
    assert hasattr(result, "count"), "BGP Table missing count"
    assert result.count > 0, "BGP Table count is 0"


@pytest.mark.dependency(**DEPENDS_KWARGS)
def test_juniper_bgp_route_direct():
    with DIRECT.open("r") as file:
        sample = file.read()
    return _tester(sample)


@pytest.mark.dependency(**DEPENDS_KWARGS)
def test_juniper_bgp_route_indirect():
    with INDIRECT.open("r") as file:
        sample = file.read()
    return _tester(sample)


@pytest.mark.dependency(**DEPENDS_KWARGS)
def test_juniper_bgp_route_aspath():
    with AS_PATH.open("r") as file:
        sample = file.read()
    return _tester(sample)


def test_juniper_bgp_route_asdot():
    sample = DIRECT.read_text().replace("1299 13335 I", "1299 65000.100 I")
    result = _parse(sample)

    assert result.routes[0].as_path == [1299, 4259840100]


def test_juniper_bgp_route_confederation():
    sample = DIRECT.read_text().replace("1299 13335 I", "(65527) 1299 13335 I")
    result = _parse(sample)

    assert result.routes[0].as_path == [1299, 13335]


OTC = Path(__file__).parent / "fixtures" / "juniper-live" / "community4-otc.xml"


def test_juniper_bgp_route_otc():
    """Two `<bgp-path-attributes>` blocks on an OTC route parse as one (#133)."""
    table = parse_juniper([OTC.read_text()])

    assert [route.prefix for route in table.routes] == ["1.0.0.0/24", "8.44.61.0/24"]
    otc = table.routes[1]
    assert otc.as_path == [65000, 37239, 13335]
    assert otc.source_as == 13335
    assert otc.source_rid == "0.90.0.146"
    assert otc.communities == ["37195:302"]


def test_juniper_bgp_route_unexpected_error():
    """An unexpected parse fault surfaces as a ParsingError with a cause (#133)."""
    with pytest.raises(ParsingError) as exc:
        with patch(
            "hyperglass.plugins._builtin.bgp_route_juniper.JuniperBGPTable",
            side_effect=AttributeError("boom"),
        ):
            parse_juniper([OTC.read_text()])

    assert isinstance(exc.value.__cause__, AttributeError)
