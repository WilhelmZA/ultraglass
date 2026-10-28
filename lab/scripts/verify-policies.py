#!/usr/bin/env python3
# ruff: noqa: S101 -- This script is an integration test.
"""Replay captured BGP routes against live RPKI and enrichment providers (#22).

Requires development dependencies. Redis is isolated in memory; external
providers are real. This checks model data, not browser rendering.
"""

import argparse
import asyncio
import json
from pathlib import Path

import fakeredis

from hyperglass.state import manager, use_state
from hyperglass.models.config.params import Params
from hyperglass.plugins._builtin.bgp_route_arista import parse_arista
from hyperglass.plugins._builtin.bgp_route_frr import parse_frr
from hyperglass.plugins._builtin.bgp_routestr_huawei import parse_huawei
from hyperglass.plugins._builtin.bgp_route_enrichment import ZBgpRouteEnrichment


def main():
    """Verify community policies, provider results, and deferred enrichment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routinator", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    server = fakeredis.FakeServer()
    manager.Redis = lambda **kwargs: fakeredis.FakeRedis(server=server)
    use_state().redis.set("params", Params())
    params = use_state("params")
    params.structured.rpki.mode = "external"
    params.structured.rpki.rpki_server_url = args.routinator
    params.structured.ip_enrichment.enrich_bgproute = True
    root = Path(__file__).resolve().parents[2] / "hyperglass/plugins/tests/fixtures"
    samples = [
        ("arista", parse_arista, "arista_live_route.json"),
        ("frr", parse_frr, "frr-live/route4.txt"),
        ("huawei", parse_huawei, "huawei-vrp/route4.txt"),
    ]
    results = []
    for backend in ("cloudflare", "routinator"):
        params.structured.rpki.backend = backend
        for policy in ("deny", "permit", "name"):
            params.structured.communities.names = {"37195:302": "Lab community"}
            params.structured.communities.items = ["^37195:302$"]
            params.structured.communities.mode = policy
            for mode in ("inline", "async"):
                params.structured.ip_enrichment.mode = mode
                for name, parse, filename in samples:
                    table = parse(((root / filename).read_text(),))
                    table = ZBgpRouteEnrichment().process(output=table, query=None)
                    if mode == "async":
                        assert not table.asn_organizations
                        asyncio.run(table.enrich_as_path_organizations())
                        asyncio.run(table.enrich_with_ip_enrichment())
                    assert table.count == 1
                    route = table.routes[0]
                    assert route.rpki_state == 1, (backend, name, route.rpki_state)
                    expected = {
                        "deny": [],
                        "permit": ["37195:302"],
                        "name": ["37195:302,Lab community"],
                    }[policy]
                    assert route.communities == expected
                    organization = table.asn_organizations.get("13335", {}).get("name")
                    assert organization and organization != "AS13335", organization
                    row = {
                        "platform": name,
                        "backend": backend,
                        "policy": policy,
                        "mode": mode,
                        "rpki": route.rpki_state,
                        "organization": organization,
                    }
                    results.append(row)
                    print(row, flush=True)
    args.output.write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
