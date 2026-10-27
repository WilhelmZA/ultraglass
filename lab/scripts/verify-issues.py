#!/usr/bin/env python3
"""Verify issue regressions through a running lab API and retain response evidence."""

import argparse
import concurrent.futures
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def query(api, device, directive, target, timeout=330):
    """Run one HTTP query and retain its status, response, and duration."""
    endpoint = urllib.parse.urlsplit(api)
    if endpoint.scheme not in ("http", "https") or not endpoint.netloc:
        raise ValueError("The API URL must use HTTP or HTTPS")
    body = {"queryLocation": device, "queryType": directive, "queryTarget": target}
    request = urllib.request.Request(  # noqa: S310 - Scheme validated above.
        f"{api}/query", json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            status, result = response.status, json.load(response)
    except urllib.error.HTTPError as error:
        status, result = error.code, json.load(error)
    except (OSError, ValueError) as error:
        status, result = 0, {"error": str(error)}
    return {
        "request": body,
        "status": status,
        "seconds": round(time.monotonic() - started, 2),
        "response": result,
    }


def cases(devices):
    """Include foreign directive IDs to exercise mixed-vendor resolution."""
    for device in devices:
        for kind, target in (
            ("bgp_route_table", "1.1.1.1"),
            ("bgp_route_table", "2606:4700::1111"),
            ("bgp_aspath_table", "_13335$"),
            ("bgp_community_table", "37195:302"),
            ("ping", "1.1.1.1"),
            ("traceroute", "1.1.1.1"),
        ):
            yield device, f"__hyperglass_arista_eos_{kind}__", target, False
        for kind in ("bgp_aspath", "bgp_community"):
            yield device, f"__hyperglass_frr_{kind}__", '13335"; id; #', True


def main():
    """Run the selected device matrix and save its evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8002/api")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("devices", nargs="+", help="Lab device IDs")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    def run(case):
        device, directive, target, reject = case
        result = query(args.api, device, directive, target)
        response = result["response"]
        output = response.get("output")
        passed = (
            (result["status"] == 400 and response.get("level") == "warning")
            if reject
            else (result["status"] in (200, 201) and response.get("level") == "success")
        )
        if not reject and isinstance(output, dict):
            entries = output.get("routes", output.get("hops"))
            passed = passed and bool(entries)
        result["expected_rejection"] = reject
        result["passed"] = passed
        if isinstance(output, dict):
            count = len(output.get("routes", output.get("hops", [])))
            shape = f"structured entries={count}"
        else:
            shape = f"text bytes={len(str(output or ''))}"
        print(
            f"{device} {directive} {target!r}: {'PASS' if passed else 'FAIL'} "
            f"{result['seconds']}s {shape}",
            flush=True,
        )
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(run, cases(args.devices)))
    (args.output / "results.json").write_text(json.dumps(results, indent=2))
    raise SystemExit(0 if all(r["passed"] for r in results) else 1)


if __name__ == "__main__":
    main()
