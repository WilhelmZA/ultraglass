"""Feature coverage for every lab device, one case per (device, query).

Each case asserts the shape Ultraglass should return from a real device holding
a full table. Cases for known, filed bugs are marked xfail with the issue
number, so the suite stays green until a fix lands and then flags the xpass.

Expectation kinds:
  structured  output is a dict with a non-empty routes[] or hops[] list
  text        level success and output is a non-empty string with no error marker
  empty       level warning with the "no matching results" message
  no_table    as empty on the structured instance; skipped on the text instance,
              where the device prints its table header even with no match

The suite runs against the structured instance (8001) by default. Set
ULTRAGLASS_LAB_TEXT=1 with ULTRAGLASS_LAB_API=http://127.0.0.1:8002/api to run
it against the text instance: `_table` ids become their text ids and every
structured case expects text.

The lab core NATs IPv4 out to the host but has no IPv6 egress. IPv6 ping and
traceroute cases use VRF targets inside the lab, and IOL, which answers with
text even when the probes time out.
"""
import time

import pytest

from conftest import TEXT, query

V4 = "1.1.1.1"
V6 = "2606:4700::1111"
# IOS has no longest-match IPv6 BGP lookup, so its rule needs a prefix (PR #85).
V6_PREFIX = "2606:4700::/44"
ASPATH = "_13335$"
COMMUNITY = "37195:302"

# Each VRF `LAB` holds one locally originated route with an empty AS path.
VRF_V4 = "198.51.100.1"
VRF_V6 = "2001:db8:100::1"
VRF_NO_MATCH_ASPATH = "_65001$"

ERROR_MARKERS = (
    "Error parsing",
    "Permission denied",
    "% Invalid input",
    "privileged mode required",
    "syntax error",
    "Unrecognized",
)


def _huawei_vrf(v4, v6):
    """VRF cases for a Huawei node, whose VRF loopback is `v4` / `v6`."""
    return [
        ("__hyperglass_huawei_bgp_route_table__", "bgp_route_v4", VRF_V4, "structured", None),
        ("__hyperglass_huawei_bgp_route_table__", "bgp_route_v6", VRF_V6, "structured", None),
        ("__hyperglass_huawei_ping__", "ping_v4", v4, "text", None),
        ("__hyperglass_huawei_ping__", "ping_v6", v6, "text", None),
        ("__hyperglass_huawei_traceroute__", "traceroute_v4", v4, "structured", None),
        ("__hyperglass_huawei_traceroute__", "traceroute_v6", v6, "structured", None),
    ]


# device -> list of (query_type, label, target, expectation, xfail_issue)
MATRIX = {
    "lab-frr": [
        ("__hyperglass_frr_bgp_route_table__", "bgp_route_v4", V4, "structured", None),
        ("__hyperglass_frr_bgp_route_table__", "bgp_route_v6", V6, "structured", None),
        ("__hyperglass_frr_bgp_aspath_table__", "bgp_aspath", ASPATH, "structured", None),
        ("__hyperglass_frr_bgp_community_table__", "bgp_community", COMMUNITY, "structured", None),
        ("__hyperglass_frr_ping__", "ping_v4", V4, "text", None),
        ("__hyperglass_frr_traceroute__", "traceroute_v4", V4, "structured", None),
    ],
    # FRR has no VRF form of ping or traceroute, so the VRF location drops them.
    "lab-frr-vrf": [
        ("__hyperglass_frr_bgp_route_table__", "bgp_route_v4", VRF_V4, "structured", None),
        ("__hyperglass_frr_bgp_route_table__", "bgp_route_v6", VRF_V6, "structured", None),
        ("__hyperglass_frr_bgp_aspath_table__", "bgp_aspath_no_match", VRF_NO_MATCH_ASPATH, "empty", None),
    ],
    "lab-bird": [
        ("__hyperglass_bird_bgp_route_table__", "bgp_route_v4", V4, "structured", None),
        ("__hyperglass_bird_bgp_route_table__", "bgp_route_v6", V6, "structured", None),
        ("__hyperglass_bird_bgp_aspath_table__", "bgp_aspath", ASPATH, "structured", None),
        ("__hyperglass_bird_bgp_community_table__", "bgp_community", COMMUNITY, "structured", None),
        ("__hyperglass_bird_ping__", "ping_v4", V4, "text", None),
        ("__hyperglass_bird_traceroute__", "traceroute_v4", V4, "structured", None),
    ],
    "lab-openbgpd": [
        ("__hyperglass_openbgpd_bgp_route_table__", "bgp_route_v4", V4, "structured", None),
        ("__hyperglass_openbgpd_bgp_route_table__", "bgp_route_v6", V6, "structured", None),
        ("__hyperglass_openbgpd_bgp_aspath_table__", "bgp_aspath", ASPATH, "structured", None),
        ("__hyperglass_openbgpd_bgp_community_table__", "bgp_community", COMMUNITY, "structured", None),
        ("__hyperglass_openbgpd_ping__", "ping_v4", V4, "text", None),
        ("__hyperglass_openbgpd_traceroute__", "traceroute_v4", V4, "structured", None),
    ],
    "lab-mikrotik": [
        ("__hyperglass_mikrotik_bgp_route_table__", "bgp_route_v4", V4, "structured", None),
        ("__hyperglass_mikrotik_bgp_route_table__", "bgp_route_v6", V6, "structured", None),
        ("__hyperglass_mikrotik_bgp_aspath_table__", "bgp_aspath", ASPATH, "structured", None),
        ("__hyperglass_mikrotik_bgp_community_table__", "bgp_community", COMMUNITY, "structured", None),
        ("__hyperglass_mikrotik_ping__", "ping_v4", V4, "text", None),
        ("__hyperglass_mikrotik_traceroute__", "traceroute_v4", V4, "structured", None),
    ],
    "lab-vyos": [
        ("__hyperglass_vyos_bgp_route_table__", "bgp_route_v4", V4, "structured", None),
        ("__hyperglass_vyos_bgp_route_table__", "bgp_route_v6", V6, "structured", None),
        ("__hyperglass_vyos_bgp_aspath_table__", "bgp_aspath", ASPATH, "structured", None),
        ("__hyperglass_vyos_bgp_community_table__", "bgp_community", COMMUNITY, "structured", None),
        ("__hyperglass_vyos_ping__", "ping_v4", V4, "text", None),
        ("__hyperglass_vyos_traceroute__", "traceroute_v4", V4, "structured", None),
    ],
    "lab-arista": [
        ("__hyperglass_arista_eos_bgp_route_table__", "bgp_route_v4", V4, "structured", None),
        ("__hyperglass_arista_eos_bgp_route_table__", "bgp_route_v6", V6, "structured", None),
        ("__hyperglass_arista_eos_bgp_aspath_table__", "bgp_aspath", ASPATH, "structured", None),
        ("__hyperglass_arista_eos_bgp_community_table__", "bgp_community", COMMUNITY, "structured", None),
        ("__hyperglass_arista_eos_ping__", "ping_v4", V4, "text", None),
        # The shared standard traceroute parser now gives Arista structured hops.
        ("__hyperglass_arista_eos_traceroute__", "traceroute_v4", V4, "structured", None),
    ],
    "lab-arista-vrf": [
        ("__hyperglass_arista_eos_bgp_route_table__", "bgp_route_v4", VRF_V4, "structured", None),
        ("__hyperglass_arista_eos_bgp_route_table__", "bgp_route_v6", VRF_V6, "structured", None),
        ("__hyperglass_arista_eos_bgp_aspath_table__", "bgp_aspath_no_match", VRF_NO_MATCH_ASPATH, "no_table", None),
        ("__hyperglass_arista_eos_ping__", "ping_v4", "192.0.2.100", "text", None),
        ("__hyperglass_arista_eos_ping__", "ping_v6", VRF_V6, "text", None),
        ("__hyperglass_arista_eos_traceroute__", "traceroute_v4", "192.0.2.100", "structured", None),
        ("__hyperglass_arista_eos_traceroute__", "traceroute_v6", VRF_V6, "structured", None),
    ],
    # Huawei CE12800 V200R005C10SPC607B607, which runs VRP 8.180 (platform
    # huawei_vrpv8). A full table crashes the slow emulated
    # control plane, so the lab caps what the core sends it (see lab-up.sh /
    # gobgpd.toml). Detailed and brief BGP formats have captured regression
    # coverage; AS-path and community queries must return routes (issue #20).
    "lab-huawei-vrpv8": [
        ("__hyperglass_huawei_bgp_route_table__", "bgp_route_v4", V4, "structured", None),
        ("__hyperglass_huawei_bgp_route_table__", "bgp_route_v6", V6, "structured", None),
        ("__hyperglass_huawei_bgp_aspath_table__", "bgp_aspath", ASPATH, "structured", None),
        ("__hyperglass_huawei_bgp_community_table__", "bgp_community", COMMUNITY, "structured", None),
        ("__hyperglass_huawei_ping__", "ping_v4", V4, "text", None),
        ("__hyperglass_huawei_traceroute__", "traceroute_v4", V4, "structured", None),
    ],
    "lab-huawei-vrpv8-vrf": _huawei_vrf("192.0.2.108", "2001:db8:100::8"),
    # NE40E V800R011C00SPC607B607, also VRP 8.180, with the same capped feed (#103).
    "lab-huawei-ne40": [
        ("__hyperglass_huawei_bgp_route_table__", "bgp_route_v4", V4, "structured", None),
        ("__hyperglass_huawei_bgp_route_table__", "bgp_route_v6", V6, "structured", None),
        ("__hyperglass_huawei_bgp_aspath_table__", "bgp_aspath", ASPATH, "structured", None),
        ("__hyperglass_huawei_bgp_community_table__", "bgp_community", COMMUNITY, "structured", None),
        ("__hyperglass_huawei_ping__", "ping_v4", V4, "text", None),
        ("__hyperglass_huawei_traceroute__", "traceroute_v4", V4, "structured", None),
    ],
    "lab-huawei-ne40-vrf": _huawei_vrf("192.0.2.111", "2001:db8:100::11"),
    "lab-iol": [
        ("__hyperglass_cisco_ios_bgp_route_table__", "bgp_route_v4", V4, "structured", None),
        ("__hyperglass_cisco_ios_bgp_route_table__", "bgp_route_v6", V6_PREFIX, "structured", None),
        ("__hyperglass_cisco_ios_bgp_aspath_table__", "bgp_aspath", ASPATH, "structured", None),
        ("__hyperglass_cisco_ios_bgp_community_table__", "bgp_community", COMMUNITY, "structured", None),
        ("__hyperglass_cisco_ios_ping__", "ping_v4", V4, "text", None),
        ("__hyperglass_cisco_ios_ping__", "ping_v6", V6, "text", None),
        ("__hyperglass_cisco_ios_traceroute__", "traceroute_v4", V4, "structured", None),
        ("__hyperglass_cisco_ios_traceroute__", "traceroute_v6", V6, "structured", None),
    ],
    # IOL-L2 has `structured_output: false`, so it offers text ids on both instances.
    "lab-ioll2": [
        ("__hyperglass_cisco_ios_bgp_route__", "bgp_route_v4", V4, "text", None),
        ("__hyperglass_cisco_ios_bgp_route__", "bgp_route_v6", V6_PREFIX, "text", None),
        ("__hyperglass_cisco_ios_bgp_aspath__", "bgp_aspath", ASPATH, "text", None),
        ("__hyperglass_cisco_ios_bgp_community__", "bgp_community", COMMUNITY, "text", None),
        ("__hyperglass_cisco_ios_ping__", "ping_v4", V4, "text", None),
        ("__hyperglass_cisco_ios_ping__", "ping_v6", V6, "text", None),
        ("__hyperglass_cisco_ios_traceroute__", "traceroute_v4", V4, "text", None),
        ("__hyperglass_cisco_ios_traceroute__", "traceroute_v6", V6, "text", None),
    ],
}


def _cases():
    for device, rows in MATRIX.items():
        for query_type, label, target, expect, issue in rows:
            if TEXT:
                if expect == "no_table":
                    continue
                # The text instance offers no `_table` ids (#145).
                query_type = query_type.replace("_table__", "__")
                if expect == "structured":
                    expect = "text"
            elif expect == "no_table":
                expect = "empty"
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
    if expect == "empty":
        return True
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
        if TEXT:
            # A text device must not show raw JSON or XML (#145).
            assert not output.lstrip().startswith(("{", "[", "<")), f"raw output: {output[:120]}"
    elif expect == "empty":
        assert level == "warning", f"level={level} output={str(output)[:120]}"
        assert "no matching results" in str(output), f"output={str(output)[:120]}"
    else:
        raise AssertionError(f"unknown expectation {expect}")
