#!/usr/bin/env python3
"""Start an existing main-lab container and restore its Containerlab links."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import yaml

LAB = Path(__file__).resolve().parents[1]
PREFIX = "clab-ultraglass-"


def run(*args, check=True):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        raise RuntimeError(f"{' '.join(args)}: {result.stderr or result.stdout}")
    return result


def inspect(name):
    result = run("docker", "inspect", PREFIX + name, check=False)
    return json.loads(result.stdout)[0] if result.returncode == 0 else None


def interface(node, name):
    result = run(
        "docker", "exec", PREFIX + node, "ip", "-j", "link", "show", "dev", name, check=False
    )
    return json.loads(result.stdout)[0] if result.returncode == 0 else None


def start(node, timeout=600):
    topology = yaml.safe_load((LAB / "ultraglass-lab.clab.yml").read_text())["topology"]
    if node not in topology["nodes"]:
        raise ValueError(f"Unknown lab node: {node}")
    state = inspect(node)
    if state is None:
        raise RuntimeError(f"{node} is not deployed; use lab-up.sh first")
    if not state["State"]["Running"]:
        available = (
            int(
                next(
                    line.split()[1]
                    for line in Path("/proc/meminfo").read_text().splitlines()
                    if line.startswith("MemAvailable:")
                )
            )
            // 1024
        )
        reserve = {"junos": 6144, "huawei": 4096, "mikrotik": 2048, "iol": 4096, "ioll2": 4096}.get(
            node, 2048
        )
        if available < reserve + 12288:
            raise RuntimeError(f"Not enough RAM to start {node}: {available} MiB available")
        # Docker retains stopped containers' assigned IPv6 addresses while the
        # allocator can reuse them. Reconnect using the topology's fixed address.
        definition = topology["nodes"][node]
        network = "ultraglass-mgmt"
        endpoint = state["NetworkSettings"]["Networks"].get(network)
        desired4 = definition["mgmt-ipv4"]
        desired6 = definition.get("mgmt-ipv6", "fd00:250:ffff::" + desired4.rsplit(".", 1)[1])
        ipam = (endpoint or {}).get("IPAMConfig") or {}
        if ipam.get("IPv4Address") != desired4 or ipam.get("IPv6Address") != desired6:
            if endpoint:
                run("docker", "network", "disconnect", "-f", network, PREFIX + node)
            run(
                "docker",
                "network",
                "connect",
                "--ip",
                desired4,
                "--ip6",
                desired6,
                network,
                PREFIX + node,
            )
        (LAB / "data").mkdir(exist_ok=True)
        if node == "mikrotik":
            # Patch the existing container too, retaining its original disk.
            run(
                "docker",
                "cp",
                str(LAB / "images/mikrotik/bootstrap.py"),
                PREFIX + node + ":/lab_bootstrap.py",
            )
            run("docker", "cp", PREFIX + node + ":/launch.py", str(LAB / "data/mikrotik-launch.py"))
            launcher = LAB / "data/mikrotik-launch.py"
            source = launcher.read_text()
            if "from lab_bootstrap import bootstrap_spin" not in source:
                source = source.replace(
                    'if __name__ == "__main__":',
                    'from lab_bootstrap import bootstrap_spin\nROS_vm.bootstrap_spin = bootstrap_spin\n\nif __name__ == "__main__":',
                )
                launcher.write_text(source)
                run("docker", "cp", str(launcher), PREFIX + node + ":/launch.py")
        if node == "huawei":
            launcher = LAB / "data/huawei-launch.py"
            run("docker", "cp", PREFIX + node + ":/launch.py", str(launcher))
            run(sys.executable, str(LAB / "images/huawei/patch-launcher.py"), str(launcher))
            run("docker", "cp", str(launcher), PREFIX + node + ":/launch.py")
        run("docker", "start", PREFIX + node)
    if node in ("iol", "ioll2"):
        # IOL consumes raw Ethernet frames. Offloaded host TCP checksums are not
        # completed by a hardware NIC on this path after Docker recreates eth0.
        peer_index = int(
            run("docker", "exec", PREFIX + node, "cat", "/sys/class/net/eth0/iflink").stdout
        )
        links = json.loads(run("ip", "-j", "link").stdout)
        peer = next(link["ifname"] for link in links if link["ifindex"] == peer_index)
        run("sudo", "-n", "ethtool", "-K", peer, "tx", "off")
    repaired = set()
    for link in topology["links"]:
        ends = [endpoint.split(":") for endpoint in link["endpoints"]]
        if node not in [end[0] for end in ends]:
            continue
        if not all((inspect(name) or {}).get("State", {}).get("Running") for name, _ in ends):
            continue
        interfaces = [interface(*end) for end in ends]
        if all(item and "LOWER_UP" in item["flags"] for item in interfaces):
            continue
        for (name, port), item in zip(ends, interfaces):
            if item:
                run("docker", "exec", PREFIX + name, "ip", "link", "delete", port, check=False)
        run(
            "sudo",
            "-n",
            "containerlab",
            "tools",
            "veth",
            "create",
            "-a",
            PREFIX + ":".join(ends[0]),
            "-b",
            PREFIX + ":".join(ends[1]),
        )
        repaired.update(name for name, _ in ends)
        for name, port in ends:
            if name != "core" and port.startswith("eth"):
                tap = "tap" + port.removeprefix("eth")
                if interface(name, tap):
                    # The peer can remain running while the core is restarted.
                    # Refresh redirects that still hold the deleted veth ifindex.
                    for device in (port, tap):
                        run(
                            "docker",
                            "exec",
                            PREFIX + name,
                            "tc",
                            "qdisc",
                            "del",
                            "dev",
                            device,
                            "clsact",
                            check=False,
                        )
                    run("docker", "exec", PREFIX + name, "/etc/tc-tap-ifup", tap)
            if name == "core":
                number = int(port.removeprefix("eth"))
                for address in (f"10.250.{number}.0/31", f"fd00:250:{number}::/127"):
                    run(
                        "docker",
                        "exec",
                        PREFIX + name,
                        "ip",
                        "addr",
                        "replace",
                        address,
                        "dev",
                        port,
                    )
    # Reapply ephemeral Linux addresses and VRFs after any restart or link repair.
    for name in repaired | {node}:
        if name not in ("frr", "bird", "openbgpd"):
            continue
        for command in topology["nodes"][name].get("exec", []):
            command = command.replace("ip addr add ", "ip addr replace ")
            result = run("docker", "exec", PREFIX + name, "sh", "-c", command, check=False)
            if result.returncode and not (
                "ip link add LAB" in command and "File exists" in result.stderr
            ):
                raise RuntimeError(f"{name}: {command}: {result.stderr}")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = inspect(node)["State"]
        if not state["Running"]:
            raise RuntimeError(f"{node} exited during boot")
        health = state.get("Health", {}).get("Status")
        if health is None or health == "healthy":
            python = LAB.parent / ".venv/bin/python3"
            if not python.exists():
                python = Path(sys.executable)
            if node == "huawei":
                run(
                    str(python),
                    str(LAB / "scripts/check-node.py"),
                    node,
                    "--management-only",
                    "--timeout",
                    "300",
                )
                run(str(python), str(LAB / "scripts/configure-huawei.py"))
            result = run(str(python), str(LAB / "scripts/check-node.py"), node)
            print(result.stdout.strip(), flush=True)
            return
        time.sleep(3)
    raise TimeoutError(f"{node}: boot health did not pass within {timeout}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("node")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    start(args.node, args.timeout)
