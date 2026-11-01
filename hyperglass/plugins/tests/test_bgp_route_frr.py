"""FRR BGP Route Parsing Tests."""

# flake8: noqa
# Standard Library
import json
from copy import deepcopy
from pathlib import Path

# Third Party
import pytest

# Project
from hyperglass.models.config.devices import Device
from hyperglass.models.data.bgp_route import BGPRouteTable
from hyperglass.exceptions.private import ParsingError

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


@pytest.mark.parametrize("vrf", ("default", "lab"))
@pytest.mark.parametrize("family", (4, 6))
def test_cumulus_community_prefix_metadata(vrf, family):
    sample = (FIXTURES / "cumulus-vx54-live" / f"{vrf}-community{family}.json").read_text()
    result = _process_vrf([sample], platform="cumulus_linux", vrf="CONFIGURED")

    assert result.count == 1
    assert result.vrf == ("LAB" if vrf == "lab" else "default")
    route = result.routes[0]
    assert route.as_path == ([64999, 64497] if vrf == "lab" else [64999, 13335])
    assert route.communities == ["65000:777", "65000:777:1"]
    assert route.active is True
    subnet = 2 if vrf == "lab" else 1
    assert route.next_hop == (
        f"10.252.{subnet}.2" if family == 4 else f"2001:db8:252:{subnet}::2"
    )
    expected = {
        "default": {4: "1.0.0.0/24", 6: "2606:4700:4700::/48"},
        "lab": {4: "198.51.100.0/24", 6: "2001:db8:100::/48"},
    }
    assert str(route.prefix) == expected[vrf][family]


def test_cumulus_community_combines_captured_families():
    outputs = [
        (FIXTURES / "cumulus-vx54-live" / f"lab-community{family}.json").read_text()
        for family in (4, 6)
    ]
    result = _process_vrf(outputs, platform="cumulus_linux", vrf="CONFIGURED")
    assert result.count == 2
    assert result.vrf == "LAB"
    assert {str(route.prefix) for route in result.routes} == {
        "198.51.100.0/24",
        "2001:db8:100::/48",
    }


def test_cumulus_metadata_preserves_all_paths():
    # Synthetic multipath variant; no extra live path is claimed.
    data = json.loads((FIXTURES / "cumulus-vx54-live/default-community4.json").read_text())
    paths = data["routes"]["1.0.0.0/24"]
    other = deepcopy(paths[1])
    other["bestpath"]["overall"] = False
    other["med"] = 42
    paths.append(other)
    result = _process_vrf([json.dumps(data)], platform="cumulus_linux")
    assert result.count == 2
    assert [route.med for route in result.routes] == [0, 42]
    assert [route.active for route in result.routes] == [True, False]


@pytest.mark.parametrize(
    "case", ("mismatch", "path_field", "bad_advertised", "later_header", "bad_path")
)
def test_cumulus_metadata_does_not_hide_malformed_paths(case):
    # Synthetic mutations of a captured reply are not live acceptance evidence.
    data = json.loads((FIXTURES / "cumulus-vx54-live/default-community4.json").read_text())
    paths = data["routes"]["1.0.0.0/24"]
    if case == "mismatch":
        paths[0]["prefix"] = "192.0.2.0/24"
    elif case == "path_field":
        paths[0]["valid"] = True
    elif case == "bad_advertised":
        paths[0]["advertisedTo"] = []
    elif case == "later_header":
        paths.reverse()
    else:
        del paths[1]["valid"]

    with pytest.raises(ParsingError):
        _process_vrf([json.dumps(data)], platform="cumulus_linux")
