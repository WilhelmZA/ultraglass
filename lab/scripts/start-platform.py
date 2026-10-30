#!/usr/bin/env python3
"""Restart the current optional deployment without replacing its appliance disk."""

import argparse
import importlib.util
from pathlib import Path
import time

import yaml

LAB = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("start_node", LAB / "scripts/start-node.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
helper.PREFIX = "clab-ultraglass-platforms-"
run, inspect, interface = helper.run, helper.inspect, helper.interface


def start(node):
    topology = yaml.safe_load((LAB / "data/platforms/active.clab.yml").read_text())["topology"]
    if set(topology["nodes"]) != {"probe", node}:
        raise RuntimeError("The saved companion deployment does not match the requested appliance")
    restore_probe = False
    for name in (node, "probe"):
        state = inspect(name)
        if state is None:
            raise RuntimeError(f"{name} is missing from the companion deployment")
        if state["State"]["Running"]:
            continue
        if name == "routeros6":
            run(
                "docker",
                "cp",
                str(LAB / "images/mikrotik/bootstrap.py"),
                helper.PREFIX + name + ":/lab_bootstrap.py",
            )
            launcher = LAB / "data/platforms/routeros6-launch.py"
            run("docker", "cp", helper.PREFIX + name + ":/launch.py", str(launcher))
            source = launcher.read_text()
            if "from lab_bootstrap import bootstrap_spin" not in source:
                source = source.replace(
                    'if __name__ == "__main__":',
                    'from lab_bootstrap import bootstrap_spin\nROS_vm.bootstrap_spin = bootstrap_spin\n\nif __name__ == "__main__":',
                )
                launcher.write_text(source)
                run("docker", "cp", str(launcher), helper.PREFIX + name + ":/launch.py")
        run("docker", "start", helper.PREFIX + name)
        restore_probe |= name == "probe"
    for link in topology["links"]:
        ends = [endpoint.split(":") for endpoint in link["endpoints"]]
        interfaces = [interface(*end) for end in ends]
        if not all(item and "LOWER_UP" in item["flags"] for item in interfaces):
            restore_probe = True
            for (name, port), item in zip(ends, interfaces):
                if item:
                    run(
                        "docker",
                        "exec",
                        helper.PREFIX + name,
                        "ip",
                        "link",
                        "delete",
                        port,
                        check=False,
                    )
            run(
                "sudo",
                "-n",
                "containerlab",
                "tools",
                "veth",
                "create",
                "-a",
                helper.PREFIX + ":".join(ends[0]),
                "-b",
                helper.PREFIX + ":".join(ends[1]),
            )
            for name, port in ends:
                tap = "tap" + port.removeprefix("eth")
                if name != "probe" and interface(name, tap):
                    for device in (port, tap):
                        run(
                            "docker",
                            "exec",
                            helper.PREFIX + name,
                            "tc",
                            "qdisc",
                            "del",
                            "dev",
                            device,
                            "clsact",
                            check=False,
                        )
                    run("docker", "exec", helper.PREFIX + name, "/etc/tc-tap-ifup", tap)
    if not restore_probe:
        return
    deadline = time.monotonic() + 60
    while run(
        "docker", "exec", helper.PREFIX + "probe", "gobgp", "global", "rib", "summary", check=False
    ).returncode:
        if time.monotonic() >= deadline:
            raise TimeoutError("The optional BGP probe did not start")
        time.sleep(1)
    for command in topology["nodes"]["probe"]["exec"]:
        run("docker", "exec", helper.PREFIX + "probe", "sh", "-c", command)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("node")
    start(parser.parse_args().node)
