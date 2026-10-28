"""Shared fixtures for the Ultraglass lab integration tests.

These tests hit the running lab's Ultraglass API. Bring the lab up first:

    ./lab-up.sh            # whole lab
    ./lab-up.sh frr        # one device

Tests for a device that is not running are skipped, so `./lab-up.sh frr`
followed by `pytest tests/ -k frr` works.
"""
import json
import os
import subprocess
import urllib.error
import urllib.request

import pytest

API = os.environ.get("ULTRAGLASS_LAB_API", "http://127.0.0.1:8001/api")


def _get(path, timeout=10):
    with urllib.request.urlopen(f"{API}{path}", timeout=timeout) as r:
        return json.load(r)


def api_up():
    try:
        _get("/devices", timeout=5)
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def running_devices():
    """Device ids that Ultraglass knows AND whose container is running."""
    if not api_up():
        pytest.skip("Ultraglass API not reachable; bring the lab up with ./lab-up.sh")
    known = {d["id"] for d in _get("/devices")}
    out = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True
    ).stdout
    up = {n.replace("clab-ultraglass-", "") for n in out.split() if n.startswith("clab-ultraglass-")}
    # device id lab-frr maps to container clab-ultraglass-frr
    return {d for d in known if d.replace("lab-", "") in up}


def query(device, query_type, target, timeout=320):
    """POST one query; return (level, output)."""
    body = json.dumps(
        {"queryLocation": device, "queryTarget": target, "queryType": query_type}
    ).encode()
    req = urllib.request.Request(f"{API}/query", body, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        d = json.load(e)
    return d.get("level"), d.get("output")
