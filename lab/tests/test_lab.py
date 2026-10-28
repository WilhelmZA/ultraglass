"""Feature coverage for every lab device, one case per (device, query).

Each case asserts the shape Ultraglass should return from a real device holding
a full table. Cases for known, filed bugs are marked xfail with the issue
number, so the suite stays green until a fix lands and then flags the xpass.

Expectation kinds:
  structured  output is a dict with a non-empty routes[] or hops[] list
  text        level success and output is a non-empty string with no error marker

Dataplane queries (ping, traceroute) are tested IPv4 only: the lab core NATs
IPv4 out to the host, but has no IPv6 egress, so IPv6 ping/traceroute cannot
complete (a lab limitation, not an Ultraglass defect).
"""
import time

import pytest

from conftest import query

V4 = "1.1.1.1"
V6 = "2606:4700::1111"
ASPATH = "_13335$"
COMMUNITY = "37195:302"

ERROR_MARKERS = (
    "Error parsing",
    "Permission denied",
    "% Invalid input",
    "privileged mode required",
    "syntax error",
    "Unrecognized",
)

# device -> list of (query_type, label, target, expectation, xfail_issue)
MATRIX = {
    "lab-frr": [
        ("__hyperglass_frr_bgp_route_table__", "bgp_route_v4", V4, "structured", None),
        ("__hyperglass_frr_bgp_route_table__", "bgp_route_v6", V6, "structured", None),
        ("__hyperglass_frr_bgp_aspath__", "bgp_aspath", ASPATH, "text", None),
        ("__hyperglass_frr_bgp_community__", "bgp_community", COMMUNITY, "text", None),
        ("__hyperglass_frr_ping__", "ping_v4", V4, "text", None),
        ("__hyperglass_frr_traceroute__", "traceroute_v4", V4, "structured", None),
    ],
    "lab-bird": [
        ("__hyperglass_bird_bgp_route__", "bgp_route_v4", V4, "text", None),
        ("__hyperglass_bird_bgp_route__", "bgp_route_v6", V6, "text", None),
        ("__hyperglass_bird_bgp_aspath__", "bgp_aspath", ASPATH, "text", 34),
        ("__hyperglass_bird_bgp_community__", "bgp_community", COMMUNITY, "text", None),
        ("__hyperglass_bird_ping__", "ping_v4", V4, "text", None),
        ("__hyperglass_bird_traceroute__", "traceroute_v4", V4, "structured", None),
    ],
    "lab-openbgpd": [
        ("__hyperglass_openbgpd_bgp_route__", "bgp_route_v4", V4, "text", None),
        ("__hyperglass_openbgpd_bgp_route__", "bgp_route_v6", V6, "text", None),
        ("__hyperglass_openbgpd_bgp_aspath__", "bgp_aspath", ASPATH, "text", None),
        ("__hyperglass_openbgpd_bgp_community__", "bgp_community", COMMUNITY, "text", None),
        ("__hyperglass_openbgpd_ping__", "ping_v4", V4, "text", None),
        ("__hyperglass_openbgpd_traceroute__", "traceroute_v4", V4, "structured", None),
    ],
    "lab-mikrotik": [
        ("__hyperglass_mikrotik_bgp_route_table__", "bgp_route_v4", V4, "structured", None),
        ("__hyperglass_mikrotik_bgp_route_table__", "bgp_route_v6", V6, "structured", None),
        ("__hyperglass_mikrotik_bgp_aspath_table__", "bgp_aspath", ASPATH, "structured", 31),
        ("__hyperglass_mikrotik_bgp_community_table__", "bgp_community", COMMUNITY, "structured", 31),
        ("__hyperglass_mikrotik_ping__", "ping_v4", V4, "text", None),
        ("__hyperglass_mikrotik_traceroute__", "traceroute_v4", V4, "structured", None),
    ],
    "lab-vyos": [
        ("__hyperglass_vyos_bgp_route__", "bgp_route_v4", V4, "text", None),
        ("__hyperglass_vyos_bgp_route__", "bgp_route_v6", V6, "text", None),
        ("__hyperglass_vyos_bgp_aspath__", "bgp_aspath", ASPATH, "text", None),
        ("__hyperglass_vyos_bgp_community__", "bgp_community", COMMUNITY, "text", None),
        ("__hyperglass_vyos_ping__", "ping_v4", V4, "text", None),
        ("__hyperglass_vyos_traceroute__", "traceroute_v4", V4, "structured", None),
    ],
    "lab-arista": [
        ("__hyperglass_arista_eos_bgp_route_table__", "bgp_route_v4", V4, "structured", None),
        ("__hyperglass_arista_eos_bgp_route_table__", "bgp_route_v6", V6, "structured", None),
        ("__hyperglass_arista_eos_bgp_aspath_table__", "bgp_aspath", ASPATH, "structured", 32),
        ("__hyperglass_arista_eos_bgp_community_table__", "bgp_community", COMMUNITY, "structured", 32),
        ("__hyperglass_arista_eos_ping__", "ping_v4", V4, "text", 33),
        # The shared standard traceroute parser now gives Arista structured hops.
        ("__hyperglass_arista_eos_traceroute__", "traceroute_v4", V4, "structured", None),
    ],
    # Huawei CE12800 VRP (V200R005). A full table crashes the slow emulated
    # control plane, so the lab caps what the core sends it (see lab-up.sh /
    # gobgpd.toml). Detailed and brief BGP formats have captured regression
    # coverage; AS-path and community queries must return routes (issue #20).
    "lab-huawei": [
        ("__hyperglass_huawei_bgp_route_table__", "bgp_route_v4", V4, "structured", None),
        ("__hyperglass_huawei_bgp_route_table__", "bgp_route_v6", V6, "structured", None),
        ("__hyperglass_huawei_bgp_aspath_table__", "bgp_aspath", ASPATH, "structured", None),
        ("__hyperglass_huawei_bgp_community_table__", "bgp_community", COMMUNITY, "structured", None),
        ("__hyperglass_huawei_ping__", "ping_v4", V4, "text", None),
        ("__hyperglass_huawei_traceroute__", "traceroute_v4", V4, "structured", None),
    ],
}


def _cases():
    for device, rows in MATRIX.items():
        for query_type, label, target, expect, issue in rows:
            marks = []
            if issue is not None:
                marks = [pytest.mark.xfail(reason=f"issue #{issue}", strict=False)]
            yield pytest.param(
                device, query_type, target, expect,
                id=f"{device}-{label}", marks=marks,
            )


def _ready(level, output, expect):
    """True once the device can actually answer, i.e. the table has loaded."""
    if expect == "structured":
        return isinstance(output, dict) and bool(output.get("routes") or output.get("hops"))
    return level == "success" and isinstance(output, str) and bool(output.strip())


def _query_converged(device, query_type, target, expect, attempts=10, delay=20):
    """Query, retrying while a just-started device is still loading the full table.

    A cold BGP session needs a minute or more to install ~1.1M routes, so the
    first query for an in-table prefix can come back empty. Retry rather than
    fail on that race; a genuinely broken query stays empty and still fails.
    """
    for attempt in range(attempts):
        level, output = query(device, query_type, target)
        if _ready(level, output, expect) or attempt == attempts - 1:
            return level, output
        time.sleep(delay)
    return level, output


@pytest.mark.parametrize("device,query_type,target,expect", list(_cases()))
def test_query(device, query_type, target, expect, running_devices):
    if device not in running_devices:
        pytest.skip(f"{device} not running")

    level, output = _query_converged(device, query_type, target, expect)

    if expect == "structured":
        assert isinstance(output, dict), f"level={level} output={str(output)[:120]}"
        rows = output.get("routes", output.get("hops"))
        assert rows, f"empty structured output: {str(output)[:120]}"
    elif expect == "text":
        assert level == "success", f"level={level} output={str(output)[:120]}"
        assert isinstance(output, str) and output.strip(), "empty text output"
        marker = next((m for m in ERROR_MARKERS if m in output), None)
        assert marker is None, f"error marker {marker!r} in output: {output[:120]}"
    else:
        raise AssertionError(f"unknown expectation {expect}")
