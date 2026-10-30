#!/usr/bin/env python3
"""Verify main-lab service readiness and router management/data connectivity."""

import argparse
import json
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

from netmiko import ConnectHandler
import yaml


def check(node, timeout=180, management_only=False):
    lab = Path(__file__).resolve().parents[1]
    devices = yaml.safe_load((lab / "configs/ultraglass/devices.yaml").read_text())["devices"]
    # Both Huawei nodes run VRP 8.180, so their locations carry the platform name (#103).
    name = {"huawei": "lab-huawei-vrpv8"}.get(node, "lab-" + node)
    device = next((item for item in devices if item["name"] == name), None)
    deadline = time.monotonic() + timeout
    error = "not ready"
    while time.monotonic() < deadline:
        try:
            if node in ("ultraglass", "ultraglass-text"):
                port = 8001 if node == "ultraglass" else 8002
                with urlopen(f"http://127.0.0.1:{port}/api/info", timeout=5) as response:
                    assert json.load(response)["version"]
                with urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
                    assert response.status == 200
            elif node == "redis":
                output = subprocess.check_output(
                    ["docker", "exec", "clab-ultraglass-redis", "redis-cli", "ping"], text=True
                )
                assert output.strip() == "PONG"
            elif node == "core":
                subprocess.run(
                    ["docker", "exec", "clab-ultraglass-core", "gobgp", "global", "rib", "summary"],
                    check=True,
                    capture_output=True,
                )
            else:
                if device is None:
                    raise ValueError(f"No device definition for {node}")
                driver = {
                    "frr": "linux",
                    "bird": "linux",
                    "openbgpd": "linux",
                    "juniper": "juniper_junos",
                }.get(device["platform"], device["platform"])
                with ConnectHandler(
                    device_type=driver,
                    host=str(device["address"]),
                    **device["credential"],
                    conn_timeout=5,
                    banner_timeout=10,
                    auth_timeout=10,
                ) as conn:
                    assert conn.find_prompt().strip()
                for key in () if management_only else ("source4", "source6"):
                    target = device["attrs"][key]
                    result = subprocess.run(
                        [
                            "docker",
                            "exec",
                            "clab-ultraglass-core",
                            "ping",
                            "-c",
                            "2",
                            "-W",
                            "2",
                            target,
                        ],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode:
                        raise RuntimeError(f"{node} data link to {target} failed: {result.stdout}")
            print(f"{node}: ready", flush=True)
            return
        except Exception as exc:
            error = str(exc)
            time.sleep(3)
    raise TimeoutError(f"{node} readiness failed: {error}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("node")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--management-only", action="store_true")
    args = parser.parse_args()
    check(args.node, args.timeout, args.management_only)
