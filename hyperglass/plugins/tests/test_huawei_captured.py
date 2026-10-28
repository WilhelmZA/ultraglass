"""Captured CE12800 regressions for #20, #22 and #25."""

from pathlib import Path

import pytest

from hyperglass.state import use_state
from hyperglass.exceptions.private import ParsingError
from hyperglass.plugins._builtin.bgp_routestr_huawei import parse_huawei
from hyperglass.plugins._builtin.trace_route_huawei import parse_huawei_traceroute

FIXTURES = Path(__file__).parent / "fixtures" / "huawei-vrp"


def sample(name):
    """Read one complete device response."""
    return (FIXTURES / f"{name}.txt").read_text()


@pytest.mark.parametrize(
    "name,count",
    [
        ("aspath4", 2),
        ("aspath6", 1),
        ("community4", 40),
        ("community6", 0),
        ("route4", 1),
        ("route6", 1),
    ],
)
def test_complete_captured_tables(name, count):
    use_state("params").structured.rpki.mode = "router"
    table = parse_huawei((sample(name),))
    assert table.count == len(table.routes) == count
    for route in table.routes:
        assert route.active
        assert route.next_hop.lower() in ("10.250.8.0", "fd00:250:8::")
        assert route.rpki_state == 3  # BGP validity does not establish RPKI validity.
        if name.startswith("aspath"):
            assert route.as_path[0] == 65000
            assert route.as_path[-1] == 13335
            assert route.communities == []
        elif name == "community4":
            assert route.communities == ["37195:302"]
            assert route.as_path == []  # This format omits AS_PATH.


def test_merge_address_families():
    table = parse_huawei((sample("aspath4"), sample("aspath6")))
    assert {route.prefix for route in table.routes} == {
        "1.0.0.0/24",
        "1.1.1.0/24",
        "2606:4700::/44",
    }


def test_captured_trace_reaches_destination():
    trace = parse_huawei_traceroute(sample("trace"), "1.1.1.1", "lab-huawei")
    assert len(trace.hops) == 9
    assert trace.hops[-1].ip_address == "1.1.1.1"


def test_truncated_brief_table_is_not_success():
    text = "\n".join(sample("community4").splitlines()[:-1])
    with pytest.raises(ParsingError):
        parse_huawei((text,))


@pytest.mark.parametrize(
    "mode,expected",
    [("deny", []), ("permit", ["37195:302"]), ("name", ["37195:302,Lab community"])],
)
def test_captured_community_policy(mode, expected):
    params = use_state("params")
    params.structured.communities.names = {"37195:302": "Lab community"}
    params.structured.communities.items = ["^37195:302$"]
    params.structured.communities.mode = mode
    assert all(
        route.communities == expected for route in parse_huawei((sample("community4"),)).routes
    )
