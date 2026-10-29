#!/usr/bin/env python3
"""Run every query type against every lab device and print one line per result.

Usage: smoke-test.py [--text] [device ...]. Reads the directive IDs from the running lab.
--text queries the text instance (port 8002) instead of the structured one (port 8001).
"""

import json
import re
import subprocess
import sys
import time
import urllib.request

INSTANCES = {
    "structured": ("http://127.0.0.1:8001/api", "1"),
    "text": ("http://127.0.0.1:8002/api", "2"),
}
API, REDIS_DB = INSTANCES["structured"]
# Device name without "lab-" -> platform, where they differ.
PLATFORMS = {
    "junos": "juniper",
    "iol": "cisco_ios",
    "ioll2": "cisco_ios",
    "xrd": "cisco_xr",
    "iosv": "cisco_ios",
    "nexus": "cisco_nxos",
    "arista": "arista_eos",
    "arista-vrf": "arista_eos",
    "frr-vrf": "frr",
}

# Target per query type. Pick values that exist in the rrc19 table.
TARGETS = {
    "bgp_route": ["1.1.1.1", "2606:4700::1111"],
    "bgp_aspath": ["_13335$"],
    "bgp_community": ["37195:302"],
    "ping": ["1.1.1.1"],
    "traceroute": ["1.1.1.1", "8.8.8.8"],
}


def directives():
    raw = subprocess.run(
        ["docker", "exec", "clab-ultraglass-redis", "redis-cli", "-n", REDIS_DB, "--no-raw",
         "get", "hyperglass.state.ui_params"],
        capture_output=True, text=True, check=True,
    ).stdout
    return sorted(set(re.findall(r"__hyperglass_[a-z0-9_]+?__", raw)))


def query(device, directive, target):
    body = json.dumps({"queryLocation": device, "queryTarget": target, "queryType": directive})
    req = urllib.request.Request(f"{API}/query", body.encode(), {"Content-Type": "application/json"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as error:
        data = json.load(error)
    except TimeoutError:
        # Broad AS-path and community scans with enrichment can outlast the client.
        return "timeout", "none", time.monotonic() - started, None
    runtime = time.monotonic() - started
    output = data.get("output")
    if isinstance(output, dict):
        if "routes" in output:
            shape = f"dict routes={len(output['routes'])}"
        elif "hops" in output:
            shape = f"dict hops={len(output['hops'])}"
        else:
            shape = f"dict keys={sorted(output)[:4]}"
    else:
        text = str(output or "")
        shape = f"str lines={len(text.splitlines())}"
    return data.get("level"), shape, runtime, output


def main():
    global API, REDIS_DB
    args = sys.argv[1:]
    if args[:1] == ["--text"]:
        API, REDIS_DB = INSTANCES["text"]
        args = args[1:]
    devices = args or [d["id"] for d in json.load(urllib.request.urlopen(f"{API}/devices"))]
    ids = directives()
    for device in devices:
        platform = device.removeprefix("lab-")
        platform = PLATFORMS.get(platform, platform)
        for directive in ids:
            if device == "lab-iosv" and directive == "__hyperglass_cisco_ios_traceroute__":
                continue
            if not directive.startswith(f"__hyperglass_{platform}_"):
                continue
            kind = directive[len(f"__hyperglass_{platform}_"):-2].removesuffix("_table")
            targets = TARGETS.get(kind, [])
            if device in ("lab-xrd", "lab-iosv", "lab-nexus") and kind in ("ping", "traceroute"):
                targets = ["1.1.1.1", "2606:4700::1111"]
            for target in targets:
                if device == "lab-xrd":
                    # XRd rate-limits new SSH connections; each API query opens one.
                    time.sleep(2)
                if platform == "cisco_ios" and kind == "bgp_route" and ":" in target:
                    target = "2606:4700::/44"
                level, shape, runtime, _ = query(device, directive, target)
                print(f"{device:14} {kind:14} {target:18} {str(level):8} {runtime:6.1f}s  {shape}")
        if device == "lab-iosv":
            for target in ("1.1.1.1", "2606:4700::1111"):
                level, shape, runtime, _ = query(device, "lab-iosv-traceroute", target)
                print(f"{device:14} {'traceroute':14} {target:18} {str(level):8} {runtime:6.1f}s  {shape}")


if __name__ == "__main__":
    main()
