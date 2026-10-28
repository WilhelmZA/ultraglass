"""Run complete FRR and RouterOS device captures through their parsers (#25)."""

import json
from pathlib import Path

import pytest

from hyperglass.plugins._builtin.bgp_route_frr import parse_frr
from hyperglass.plugins._builtin.bgp_routestr_mikrotik import parse_mikrotik
from hyperglass.plugins._builtin.trace_route_standard import parse_standard_traceroute
from hyperglass.plugins._builtin.trace_route_mikrotik import parse_mikrotik_traceroute
from hyperglass.plugins._builtin.mikrotik_garbage_output import MikrotikGarbageOutput

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("family,prefix", [(4, "1.1.1.0/24"), (6, "2606:4700::/44")])
@pytest.mark.parametrize("platform", ["frr", "mikrotik"])
def test_captured_bgp(platform, family, prefix):
    if platform == "frr":
        raw = [(FIXTURES / "frr-live" / f"route{family}.txt").read_text()]
        table = parse_frr(raw)
    else:
        raw = json.loads((FIXTURES / "mikrotik-live" / f"route{family}.json").read_text())["raw"]
        table = parse_mikrotik(raw)
    assert table.count == 1
    route = table.routes[0]
    assert route.prefix == prefix
    assert route.as_path[-1] == 13335
    assert route.communities


@pytest.mark.parametrize("platform", ["frr", "mikrotik"])
def test_captured_complete_trace(platform):
    if platform == "frr":
        raw = (FIXTURES / "frr-live" / "trace.txt").read_text()
        table = parse_standard_traceroute(raw, "1.1.1.1", "lab-frr")
    else:
        raw = json.loads((FIXTURES / "mikrotik-live" / "trace.json").read_text())["raw"]
        raw = MikrotikGarbageOutput().process(output=raw, query=None)
        table = parse_mikrotik_traceroute(raw, "1.1.1.1", "lab-mikrotik")
    assert table.hops[-1].ip_address == "1.1.1.1"
    assert len(table.hops) == 9
