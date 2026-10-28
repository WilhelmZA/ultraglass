#!/usr/bin/env python3
"""Run every query type against every lab device and print one line per result.

Usage: smoke-test.py [device ...]. Reads the directive IDs from the running lab.
"""

import json
import re
import subprocess
import sys
import time
import urllib.request

API = "http://127.0.0.1:8001/api"
PLATFORMS = {"junos": "juniper", "iol": "cisco_ios", "ioll2": "cisco_ios"}

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
        ["docker", "exec", "clab-ultraglass-redis", "redis-cli", "-n", "1", "--no-raw",
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
    devices = sys.argv[1:] or [d["id"] for d in json.load(urllib.request.urlopen(f"{API}/devices"))]
    ids = directives()
    for device in devices:
        platform = device.removeprefix("lab-")
        platform = PLATFORMS.get(platform, platform)
        for directive in ids:
            if not directive.startswith(f"__hyperglass_{platform}_"):
                continue
            kind = directive[len(f"__hyperglass_{platform}_"):-2].removesuffix("_table")
            for target in TARGETS.get(kind, []):
                if platform == "cisco_ios" and kind == "bgp_route" and ":" in target:
                    target = "2606:4700::/44"
                level, shape, runtime, _ = query(device, directive, target)
                print(f"{device:14} {kind:14} {target:18} {str(level):8} {runtime:6.1f}s  {shape}")


if __name__ == "__main__":
    main()
