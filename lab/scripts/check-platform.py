#!/usr/bin/env python3
"""Wait for appliance SSH and verify the fixture data link after deployment."""

import argparse
import base64
import json
from pathlib import Path
import subprocess
import time

from netmiko import ConnectHandler

PLATFORMS = {
    "sonic": (1, "linux", "admin", "admin", "hostname"),
    "exos": (2, "extreme_exos", "admin", "admin", "show switch"),
    "voss": (3, "extreme_vsp", "admin", "Lab-Router9", "show sys-info"),
    "xrd": (4, "cisco_xr", "clab", "clab@123", "show version"),
    "iosv": (5, "cisco_ios", "admin", "Lab-Router9", "show version"),
    "nexus": (6, "cisco_nxos", "admin", "Lab-Router9", "show version"),
    "timos": (7, "nokia_sros", "admin", "Lab-Router9", "show version"),
    "routeros6": (8, "mikrotik_routeros", "admin", "Lab-Router9", "/system resource print"),
    "os9": (9, "dell_force10", "admin", "Lab-Router9", "show version"),
}


def check(node, timeout):
    number, driver, username, password, command = PLATFORMS[node]
    container = "clab-ultraglass-platforms-" + node
    deadline = time.monotonic() + timeout
    last_error = "waiting for startup"
    configured = False
    while time.monotonic() < deadline:
        state = json.loads(subprocess.check_output(["docker", "inspect", container]))[0]["State"]
        if not state["Running"]:
            raise RuntimeError(f"{node} exited during boot")
        if state.get("Health", {}).get("Status", "healthy") != "healthy":
            time.sleep(5)
            continue
        try:
            with ConnectHandler(
                device_type=driver,
                host=f"192.168.250.{20 + number}",
                username=username,
                password=password,
                conn_timeout=5,
                banner_timeout=10,
                auth_timeout=10,
            ) as conn:
                output = conn.send_command(command, read_timeout=30)
                if not output.strip():
                    raise RuntimeError("Empty SSH command result")
                if node == "sonic" and not configured:
                    fixture = Path(__file__).resolve().parents[1] / "configs/sonic/fixture.sh"
                    # Execute the fixture in one shell, preserving its error handling.
                    payload = base64.b64encode(fixture.read_bytes()).decode()
                    output = conn.send_command(
                        f"echo {payload} | base64 -d | sh; echo LAB_STATUS:$?",
                        read_timeout=90,
                        cmd_verify=False,
                    )
                    if "LAB_STATUS:0" not in output:
                        raise RuntimeError(output)
                    configured = True
            for family, target in (
                ("IPv4", f"10.251.{number}.1"),
                ("IPv6", f"fd00:251:{number}::1"),
            ):
                result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        "clab-ultraglass-platforms-probe",
                        "ping",
                        "-c",
                        "3",
                        "-W",
                        "2",
                        target,
                    ],
                    text=True,
                    capture_output=True,
                )
                if result.returncode:
                    raise RuntimeError(f"{family} data link failed: {result.stdout}{result.stderr}")
            print(f"{node}: SSH and both data links ready", flush=True)
            return
        except Exception as exc:
            last_error = str(exc)
            time.sleep(5)
    raise TimeoutError(f"{node} did not become ready within {timeout}s: {last_error}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("node", choices=PLATFORMS)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    check(args.node, args.timeout)
