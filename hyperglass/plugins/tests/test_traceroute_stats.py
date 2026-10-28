"""Hop statistics on every parser, and MikroTik traceroute honouring structured_output."""

import json
from pathlib import Path
from types import SimpleNamespace

from hyperglass.models.data.traceroute import TracerouteHop, TracerouteResult
from hyperglass.plugins._builtin.trace_route_frr import parse_frr_traceroute
from hyperglass.plugins._builtin.trace_route_mikrotik import TraceroutePluginMikrotik
from hyperglass.plugins._builtin.trace_route_standard import parse_standard_traceroute

FIXTURES = Path(__file__).parent / "fixtures"


def test_hop_derives_statistics_from_probes():
    hop = TracerouteHop(hop_number=1, rtt1=1.0, rtt2=None, rtt3=3.0, sent_count=3)
    assert (hop.loss_pct, hop.last_rtt, hop.best_rtt, hop.worst_rtt) == (33, 3.0, 1.0, 3.0)


def test_hop_keeps_native_statistics():
    hop = TracerouteHop(hop_number=1, rtt1=1.0, sent_count=10, loss_pct=0, best_rtt=0.5)
    assert (hop.loss_pct, hop.best_rtt) == (0, 0.5)


def test_standard_parser_fills_loss_sent_last_best_worst():
    result = parse_standard_traceroute(
        "1 * * *\n2 192.0.2.1 1.0 ms * 3.0 ms\n3 192.0.2.2 0.5 ms", "192.0.2.2", "test"
    )
    timeout, partial, single = result.hops
    assert (timeout.sent_count, timeout.loss_pct, timeout.last_rtt) == (3, 100, None)
    assert (partial.sent_count, partial.loss_pct, partial.best_rtt, partial.worst_rtt) == (
        3,
        33,
        1.0,
        3.0,
    )
    assert (single.sent_count, single.loss_pct, single.last_rtt) == (1, 0, 0.5)


def test_frr_parser_fills_sent_and_loss():
    result = parse_frr_traceroute(
        "traceroute to 192.0.2.2 (192.0.2.2), 30 hops max, 60 byte packets\n"
        " 1  192.0.2.1  0.084 ms\n 2  *\n 3  192.0.2.2  1.500 ms",
        "192.0.2.2",
        "test",
    )
    hops = {hop.hop_number: hop for hop in result.hops}
    assert (hops[1].sent_count, hops[1].loss_pct, hops[1].last_rtt) == (1, 0, 0.084)
    assert (hops[2].sent_count, hops[2].loss_pct) == (1, 100)


def test_mikrotik_traceroute_stays_text_when_structured_output_is_off():
    raw = json.loads((FIXTURES / "mikrotik-live" / "trace.json").read_text())["raw"]
    query = SimpleNamespace(
        query_target="1.1.1.1", device=SimpleNamespace(structured_output=False, name="lab-mikrotik")
    )
    result = TraceroutePluginMikrotik().process(output=tuple(raw), query=query)
    assert not isinstance(result, TracerouteResult)
    assert isinstance(result, tuple) and "1.1.1.1" in result[0]
