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


def test_captured_trace_in_flight_hop_is_unanswered():
    """An in-flight hop with no address shows as unanswered, not 0% loss (#138).

    The fixture is the first page (cut at the paging prompt) of a lab-mikrotik
    capture from the 2026-10-30 rc.2 lab run: RouterOS prints hop 9
    as `0%  1  0ms` with no address while its probe is still in flight.
    """
    raw = json.loads((FIXTURES / "mikrotik-live" / "trace_inflight.json").read_text())["raw"]
    raw = MikrotikGarbageOutput().process(output=raw, query=None)
    table = parse_mikrotik_traceroute(raw, "1.1.1.1", "lab-mikrotik")
    assert len(table.hops) == 9
    assert all(hop.loss_pct == 0 for hop in table.hops[:8])
    silent = table.hops[-1]
    assert silent.ip_address is None
    assert silent.loss_pct == 100
    assert silent.avg_rtt is None and silent.last_rtt is None
    assert silent.best_rtt is None and silent.worst_rtt is None
