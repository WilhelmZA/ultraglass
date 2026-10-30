#!/usr/bin/env python3
"""Apply the lab data-plane + eBGP config to a Huawei lab node.

    configure-huawei.py [huawei | huawei-ne40]

vrnetlab only bootstraps the management interface, SSH and login. The data port
and the eBGP session to the GoBGP core are configured here, after the VM is up.
Both nodes run VRP 8.180 and commit every change. The CE12800 (`huawei`) is a
switch whose GE ports are L2 by default, so its port is made routed with
`undo portswitch` before it gets an address; the NE40E (`huawei-ne40`) is a
router. Each node also gets vpn-instance LAB for its VRF location (#130, #103).
Safe to re-run: each part is skipped when the device already has it.

Needs netmiko (pip install netmiko). start-node.py calls this for both nodes.
"""

import sys

try:
    from netmiko import ConnectHandler
except ImportError:
    sys.exit("netmiko not installed; run: pip install netmiko")

NODES = {
    "huawei": {
        "host": "192.168.250.18",
        "subnet": 8,
        "port": "GE1/0/0",
        "routed": False,
        "vrf_v4": "192.0.2.108",
        "vrf_v6": "2001:db8:100::8",
    },
    "huawei-ne40": {
        "host": "192.168.250.32",
        "subnet": 11,
        "port": "Ethernet1/0/0",
        "routed": True,
        "vrf_v4": "192.0.2.111",
        "vrf_v6": "2001:db8:100::11",
    },
}
NODE = NODES[sys.argv[1] if len(sys.argv) > 1 else "huawei"]
N = NODE["subnet"]
HOST = NODE["host"]
PORT = NODE["port"]
LOCAL_V4 = f"10.250.{N}.1"
PEER_V4 = f"10.250.{N}.0"
LOCAL_V6 = f"fd00:250:{N}::1"
PEER_V6 = f"fd00:250:{N}::"
LOCAL_AS = 65000 + N
PEER_AS = 65000

# vpn-instance LAB (#130), matching the Arista and FRR VRF locations.
VRF = "LAB"
VRF_V4 = NODE["vrf_v4"]
VRF_V6 = NODE["vrf_v6"]

dev = {
    "device_type": "huawei_vrpv8",
    "host": HOST,
    "username": "admin",
    "password": "admin",
    "conn_timeout": 20,
    "banner_timeout": 30,
    "auth_timeout": 30,
    # VRP 8.180 offers legacy host-key/kex that paramiko 4 disables.
    "disabled_algorithms": {"pubkeys": ["rsa-sha2-512", "rsa-sha2-256"]},
}


def save(nc):
    """Save the configuration, answering the confirmation prompts.

    The NE40E reads `save force` as a file name, so answer the prompts instead.
    """
    out = last = nc.send_command_timing("save", read_timeout=90)
    for _ in range(3):
        if "[Y/N]" not in last.upper():
            break
        last = nc.send_command_timing("Y", read_timeout=90)
        out += last
    return out


def main():
    """Configure the data port, eBGP and vpn-instance LAB where missing."""
    nc = ConnectHandler(**dev)
    brief = nc.send_command("display ip interface brief", read_timeout=60)
    instances = nc.send_command("display ip vpn-instance", read_timeout=60)
    base_done = LOCAL_V4 in brief
    vrf_done = VRF in instances.split()
    if base_done and vrf_done:
        print(f"{HOST} already configured ({PORT} and vpn-instance {VRF}); nothing to do.")
        print(save(nc))
        nc.disconnect()
        return

    nc.config_mode()  # system-view

    def send(cmd):
        out = nc.send_command_timing(cmd, read_timeout=60, strip_prompt=False, strip_command=False)
        if "[Y/N]" in out or "Continue?" in out:
            out += nc.send_command_timing(
                "Y", read_timeout=60, strip_prompt=False, strip_command=False
            )
        return out

    base = (
        # Data port: the CE12800 GE port is a switchport by default -> make it routed.
        f"interface {PORT}",
        *(() if NODE["routed"] else ("undo portswitch",)),
        "undo shutdown",
        f"ip address {LOCAL_V4} 255.255.255.254",
        "ipv6 enable",
        f"ipv6 address {LOCAL_V6} 127",
        "quit",
        # eBGP to the GoBGP core, v4 + v6.
        f"bgp {LOCAL_AS}",
        f"router-id {LOCAL_V4}",
        f"peer {PEER_V4} as-number {PEER_AS}",
        f"peer {PEER_V6} as-number {PEER_AS}",
        "ipv4-family unicast",
        f"peer {PEER_V4} enable",
        "quit",
        "ipv6-family unicast",
        f"peer {PEER_V6} enable",
        "quit",
        "quit",
    )
    vrf = (
        # vpn-instance LAB with both address families.
        f"ip vpn-instance {VRF}",
        "ipv4-family",
        f"route-distinguisher {LOCAL_AS}:100",
        "quit",
        "ipv6-family",
        f"route-distinguisher {LOCAL_AS}:100",
        "quit",
        "quit",
        # Loopback inside the instance: the VRF location's source4/source6.
        "interface LoopBack100",
        f"ip binding vpn-instance {VRF}",
        f"ip address {VRF_V4} 255.255.255.255",
        "ipv6 enable",
        f"ipv6 address {VRF_V6} 128",
        "quit",
        # Originate the same test prefixes as the Arista and FRR VRF locations.
        f"ip route-static vpn-instance {VRF} 198.51.100.0 24 NULL0",
        f"ipv6 route-static vpn-instance {VRF} 2001:db8:100:: 48 NULL0",
        f"bgp {LOCAL_AS}",
        f"ipv4-family vpn-instance {VRF}",
        "network 198.51.100.0 24",
        "quit",
        f"ipv6-family vpn-instance {VRF}",
        "network 2001:db8:100:: 48",
        "quit",
        "quit",
    )
    for cmd in (() if base_done else base) + (() if vrf_done else vrf):
        send(cmd)

    send("commit")
    nc.exit_config_mode()
    print(save(nc))
    print(nc.send_command("display ip interface brief", read_timeout=60))
    nc.disconnect()
    print("Huawei configured.")


if __name__ == "__main__":
    main()
