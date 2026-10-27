#!/usr/bin/env python3
"""Exercise every query type for one lab device and report results.

Usage: test-device.py lab-frr frr
Reads directive IDs for the platform from the running Ultraglass, queries each
with v4 and v6 targets where relevant, and prints level + output shape + a short
excerpt. Then prints any captured errors from the sample log.
"""
import json, re, subprocess, sys, urllib.request, urllib.error

API = "http://127.0.0.1:8001/api"
device, platform = sys.argv[1], sys.argv[2]

# target choice per query kind
V4, V6 = "1.1.1.1", "2606:4700::1111"
TARGETS = {
    "bgp_route": [V4, V6], "bgp_route_table": [V4, V6],
    "bgp_aspath": ["_13335$"], "bgp_aspath_table": ["_13335$"],
    "bgp_community": ["37195:302"], "bgp_community_table": ["37195:302"],
    "ping": [V4, V6], "traceroute": [V4, V6],
}

def directives():
    raw = subprocess.run(["docker","exec","clab-ultraglass-redis","redis-cli","-n","1","--no-raw",
        "get","hyperglass.state.ui_params"], capture_output=True, text=True).stdout
    ids = sorted(set(re.findall(r"__hyperglass_[a-z0-9_]+?__", raw)))
    return [d for d in ids if d.startswith(f"__hyperglass_{platform}_")]

def kind_of(d):
    return d[len(f"__hyperglass_{platform}_"):-2]

def query(directive, target):
    body = json.dumps({"queryLocation":device,"queryTarget":target,"queryType":directive}).encode()
    req = urllib.request.Request(f"{API}/query", body, {"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r: d = json.load(r)
    except urllib.error.HTTPError as e: d = json.load(e)
    except Exception as e: return "EXC", str(e)[:60]
    o = d.get("output")
    if isinstance(o, dict):
        if "routes" in o: shape=f"dict routes={len(o['routes'])}"
        elif "hops" in o: shape=f"dict hops={len(o['hops'])}"
        else: shape=f"dict {sorted(o)[:4]}"
    else:
        t=str(o or ""); shape=f"str {len(t.splitlines())}L '{t[:55]}'"
    return d.get("level"), shape

print(f"=== {device} ({platform}) ===")
for d in directives():
    k = kind_of(d)
    for t in TARGETS.get(k, ["1.1.1.1"]):
        lvl, shape = query(d, t)
        flag = "" if lvl in ("success",) else "  <-- CHECK"
        print(f"{k:20} {t:18} {str(lvl):8} {shape}{flag}")
