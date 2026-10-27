"""Captured EOS and synthetic CLI format coverage for #35."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from hyperglass.plugins._builtin.trace_route_standard import (
    TraceroutePluginStandard,
    parse_standard_traceroute,
)


def test_captured_eos_complete_trace():
    text = (Path(__file__).parent / "fixtures" / "arista_traceroute.txt").read_text()
    result = parse_standard_traceroute(text, "1.1.1.1", "lab-arista")
    assert len(result.hops) == 9
    assert result.hops[-1].ip_address == "1.1.1.1"
    assert result.hops[4].rtt1 == 15.169
    assert result.hops[4].rtt2 == 20.812
    assert result.hops[4].rtt3 == 15.235
    assert result.raw_output == text


def test_synthetic_ipv6_and_timeout_probes():
    text = (
        "1 * * *\n2 edge.example (2001:db8::1) * 0.0 ms 2.5 ms\n3 2001:db8::2 1 msec 2 msec 3 msec"
    )
    result = parse_standard_traceroute(text, "2001:db8::2", "test")
    assert result.hops[0].is_timeout
    assert result.hops[1].rtt1 is None
    assert result.hops[1].rtt2 == 0.0
    assert result.hops[1].hostname == "edge.example"
    assert result.hops[2].ip_address == "2001:db8::2"
    assert result.hops[2].rtt3 == 3.0


@pytest.mark.parametrize("platform", ["bird", "openbgpd", "vyos"])
def test_captured_linux_traces(platform):
    text = (Path(__file__).parent / "fixtures" / f"{platform}_traceroute.txt").read_text()
    query = SimpleNamespace(
        query_target="1.1.1.1", device=SimpleNamespace(structured_output=True, name=platform)
    )
    result = TraceroutePluginStandard().process(output=(text,), query=query)
    assert len(result.hops) == 9
    assert result.hops[-1].ip_address == "1.1.1.1"
    assert result.raw_output == text


@pytest.mark.parametrize(
    "structured,text", [(False, "1 192.0.2.1 1 ms"), (True, "unrecognized output")]
)
def test_plain_or_unrecognized_output_is_preserved(structured, text):
    query = SimpleNamespace(
        query_target="192.0.2.1", device=SimpleNamespace(structured_output=structured, name="test")
    )
    assert TraceroutePluginStandard().process(output=(text,), query=query) == (text,)
