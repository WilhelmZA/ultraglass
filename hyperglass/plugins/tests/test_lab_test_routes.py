"""Parse AS-path and community captures of the lab test routes (#22, #25).

The lab core advertises 1.0.0.0/24 and 2606:4700:4700::/48 with AS path 64999 13335,
community 65000:777 and large community 65000:777:1. No other route carries them.
"""

# Standard Library
import json
from pathlib import Path

# Third Party
import pytest

# Project
from hyperglass.plugins._builtin.bgp_route_frr import parse_frr
from hyperglass.plugins._builtin.bgp_route_arista import parse_arista
from hyperglass.plugins._builtin.bgp_routestr_mikrotik import parse_mikrotik

FIXTURES = Path(__file__).parent / "fixtures"
PREFIXES = {4: "1.0.0.0/24", 6: "2606:4700:4700::/48"}


# VyOS IPv4 AS-path and community captures predate the test routes; see test_bgp_route_vyos.
@pytest.mark.parametrize("platform,family", (("frr", 4), ("frr", 6), ("vyos", 6)))
@pytest.mark.parametrize("kind", ("aspath", "community"))
def test_frr_summary_json(platform, kind, family):
    table = parse_frr([(FIXTURES / f"{platform}-live" / f"{kind}{family}.json").read_text()])
    assert [route.prefix for route in table.routes] == [PREFIXES[family]]
    route = table.routes[0]
    assert route.as_path == [65000, 64999, 13335]
    # FRR summary JSON carries no communities.
    assert route.communities == []


def test_arista_aspath6():
    table = parse_arista([(FIXTURES / "arista-live" / "aspath6.json").read_text()])
    assert [route.prefix for route in table.routes] == [PREFIXES[6]]
    assert table.routes[0].as_path == [65000, 64999, 13335]
    # EOS regexp output carries no communities.
    assert table.routes[0].communities == []


@pytest.mark.parametrize("family", (4, 6))
def test_arista_community_detail(family):
    """The address-family detail form keeps communities (#66)."""
    table = parse_arista(
        [(FIXTURES / "arista-live" / f"community{family}_detail.json").read_text()]
    )
    assert [route.prefix for route in table.routes] == [PREFIXES[family]]
    assert set(table.routes[0].communities) >= {"65000:777", "65000:777:1"}


@pytest.mark.parametrize("kind", ("aspath", "community"))
def test_mikrotik(kind):
    raw = json.loads((FIXTURES / "mikrotik-live" / f"{kind}.json").read_text())["raw"]
    table = parse_mikrotik(raw)
    assert {route.prefix for route in table.routes} == set(PREFIXES.values())
    for route in table.routes:
        assert route.as_path == [65000, 64999, 13335]
        assert set(route.communities) >= {"65000:777", "65000:777:1"}


@pytest.mark.parametrize("family", (4, 6))
def test_frr_community_detail(family):
    """`json detail` keeps communities for FRR community queries (#67)."""
    raw = (FIXTURES / "frr-live" / f"community{family}_detail.json").read_text()
    table = parse_frr([raw])
    assert [route.prefix for route in table.routes] == [PREFIXES[family]]
    assert table.routes[0].as_path == [65000, 64999, 13335]
    assert table.routes[0].communities == ["65000:777"]
