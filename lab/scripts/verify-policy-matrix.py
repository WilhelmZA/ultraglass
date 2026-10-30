#!/usr/bin/env python3
# ruff: noqa: S101, S310 -- This script is an integration test against a lab URL.
"""Check AS-path and community results against one structured-output configuration (#22).

Run it against an Ultraglass instance whose config sets the policy, RPKI backend and
enrichment mode named on the command line. The core must advertise the lab test routes:

    gobgp global rib add -a ipv4 1.0.0.0/24 nexthop 0.0.0.0 aspath "64999 13335" \
        community 65000:777 large-community 65000:777:1
    gobgp global rib add -a ipv6 2606:4700:4700::/48 nexthop :: aspath "64999 13335" \
        community 65000:777 large-community 65000:777:1

AS 64999 and community 65000:777 appear only on these routes, so each query returns a
small, known result. Cloudflare and Routinator both report the routes as RPKI valid.
"""

import argparse
import json
import time
import urllib.request
from pathlib import Path

TEST_PREFIXES = {"1.0.0.0/24", "2606:4700:4700::/48"}
# Device output that carries no communities, so the policy has nothing to act on.
# EOS `show ip bgp regexp`, Huawei brief AS-path output, FRR `regexp` JSON (FRR, VyOS)
# and the Cisco IOS, IOS-XR and NX-OS summary tables omit them.
CISCO_IOS = {"lab-iol", "lab-ioll2", "lab-xrd", "lab-nexus"}
HUAWEI = {"lab-huawei-vrpv8", "lab-huawei-ne40"}
NO_ASPATH_COMMUNITIES = {"lab-arista", *HUAWEI, "lab-frr", "lab-vyos", *CISCO_IOS}
NO_COMMUNITY_COMMUNITIES = CISCO_IOS
# Huawei brief community output omits the AS path, so RPKI and organisations cannot apply.
NO_COMMUNITY_ASPATH = HUAWEI
# Ultraglass resolves a vendor directive id to each device's equivalent by name.
QUERIES = (
    ("BGP AS Path", "__hyperglass_arista_eos_bgp_aspath_table__", "_64999_"),
    ("BGP Community", "__hyperglass_arista_eos_bgp_community_table__", "65000:777"),
)


def post(url, body):
    """Submit one query and return the decoded response."""
    request = urllib.request.Request(
        f"{url}/api/query",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=330) as response:
        return json.load(response)


def wait_for_enrichment(url, response):
    """Poll deferred enrichment until it completes and return the final output."""
    assert response["enrichment"] == "pending", response["enrichment"]
    assert not response["output"].get("asn_organizations"), "async output enriched inline"
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        with urllib.request.urlopen(
            f"{url}/api/query/{response['id']}/enrichment", timeout=30
        ) as poll:
            update = json.load(poll)
        if update["status"] != "pending":
            assert update["status"] == "complete", update["status"]
            return update["output"]
        time.sleep(1)
    raise AssertionError("enrichment did not complete")


def main():
    """Run both queries on every device and check policy, RPKI and organisation names."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8005")
    parser.add_argument("--policy", choices=("deny", "permit", "name"), required=True)
    parser.add_argument("--backend", choices=("cloudflare", "routinator"), required=True)
    parser.add_argument("--mode", choices=("inline", "async"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("devices", nargs="+")
    args = parser.parse_args()

    results = []
    for device in args.devices:
        for kind, query_type, target in QUERIES:
            body = {"queryLocation": device, "queryType": query_type, "queryTarget": target}
            response = post(args.url, body)
            assert response["level"] == "success", (device, kind, response)
            output = response["output"]
            assert isinstance(output, dict), (device, kind, "text output")
            has_path = not (kind == "BGP Community" and device in NO_COMMUNITY_ASPATH)
            if args.mode == "async" and has_path:
                output = wait_for_enrichment(args.url, response)
            routes = [r for r in output["routes"] if r["prefix"] in TEST_PREFIXES]
            assert routes, (device, kind, [r["prefix"] for r in output["routes"]])
            # Every device holds both test routes, except Huawei, which the lab feeds a
            # bounded IPv4-only subset.
            if device not in HUAWEI:
                assert {r["prefix"] for r in routes} == TEST_PREFIXES, (device, kind, routes)
            organization = output.get("asn_organizations", {}).get("13335", {}).get("name")
            if has_path:
                for route in routes:
                    assert route["rpki_state"] == 1, (device, kind, route["prefix"], route)
                    assert 64999 in route["as_path"], (device, kind, route["as_path"])
                assert organization and organization != "AS13335", (device, kind, organization)

            communities = sorted({c for r in routes for c in r["communities"]})
            expected = {
                "deny": [],
                "permit": ["65000:777"],
                "name": ["65000:777,Lab community"],
            }[args.policy]
            if kind == "BGP AS Path" and device in NO_ASPATH_COMMUNITIES:
                # The device's AS-path output carries no communities; nothing to filter.
                expected = []
            if kind == "BGP Community" and device in NO_COMMUNITY_COMMUNITIES:
                expected = []
            # Devices that report large communities keep the unlisted 65000:777:1, except
            # under `permit`, whose item list matches only the standard community.
            standard = [c for c in communities if c != "65000:777:1"]
            assert standard == expected, (device, kind, communities)
            if args.policy == "permit":
                assert "65000:777:1" not in communities, (device, kind, communities)
            row = {
                "device": device,
                "query": kind,
                "policy": args.policy,
                "backend": args.backend,
                "mode": args.mode,
                "prefixes": sorted(r["prefix"] for r in routes),
                "communities": communities,
                "rpki": sorted({r["rpki_state"] for r in routes}),
                "organization": organization,
            }
            results.append(row)
            print(json.dumps(row), flush=True)
    args.output.write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
