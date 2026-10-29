"""Captured Extreme VOSS lab output (#73)."""

# Standard Library
from pathlib import Path

# Project
from hyperglass.execution.drivers._common import command_error
from hyperglass.plugins._builtin.trace_route_standard import parse_standard_traceroute

VOSS = Path(__file__).parent / "fixtures" / "extreme-vsp-live"


def _voss(name):
    return (VOSS / f"{name}.txt").read_text()


def test_voss_trace():
    result = parse_standard_traceroute(_voss("trace4"), "1.1.1.1", "voss")
    assert len(result.hops) == 1
    hop = result.hops[0]
    assert hop.ip_address == "1.1.1.1"
    assert (hop.rtt1, hop.rtt2, hop.rtt3) == (1.55, 0.943, 1.08)
    assert hop.loss_pct == 0


def test_voss_command_error():
    assert command_error(_voss("bad"))
    for name in ("route4", "route4_empty", "route6_empty", "ping4", "trace4"):
        assert not command_error(_voss(name))
