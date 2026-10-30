#!/usr/bin/env python3
"""Apply the lab data-plane + eBGP config to the Huawei CE12800.

vrnetlab only bootstraps the CE12800's management interface, SSH and login. The
data port (GE1/0/0) and the eBGP session to the GoBGP core are configured here,
after the VM is up. The CE12800 is a two-stage-commit switch whose GE ports are
L2 by default, so the port is made routed with `undo portswitch` before it gets
an address, and every change is committed. Safe to re-run: if GE1/0/0 already
holds the lab address the script does nothing.

Needs netmiko (pip install netmiko). lab-up.sh calls this for the huawei node.
"""
import sys

try:
    from netmiko import ConnectHandler
except ImportError:
    sys.exit("netmiko not installed; run: pip install netmiko")

HOST = "192.168.250.18"
LOCAL_V4 = "10.250.8.1"
PEER_V4 = "10.250.8.0"
LOCAL_V6 = "fd00:250:8::1"
PEER_V6 = "fd00:250:8::"
LOCAL_AS = 65008
PEER_AS = 65000

dev = {
    "device_type": "huawei",
    "host": HOST,
    "username": "admin",
    "password": "admin",
    "conn_timeout": 20,
    "banner_timeout": 30,
    "auth_timeout": 30,
    # Old VRP (V200R005) offers legacy host-key/kex that paramiko 4 disables.
    "disabled_algorithms": {"pubkeys": ["rsa-sha2-512", "rsa-sha2-256"]},
}


def main():
    nc = ConnectHandler(**dev)
    brief = nc.send_command("display ip interface brief", read_timeout=60)
    if LOCAL_V4 in brief:
        print("Huawei already configured (GE1/0/0 has", LOCAL_V4 + "); nothing to do.")
        print(nc.send_command('save force', read_timeout=90))
        nc.disconnect()
        return

    nc.config_mode()  # system-view

    def send(cmd):
        out = nc.send_command_timing(
            cmd, read_timeout=60, strip_prompt=False, strip_command=False
        )
        if "[Y/N]" in out or "Continue?" in out:
            out += nc.send_command_timing(
                "Y", read_timeout=60, strip_prompt=False, strip_command=False
            )
        return out

    # Data port: GE1/0/0 is a switchport by default -> make it routed, address it.
    for cmd in (
        "interface GE1/0/0",
        "undo portswitch",
        "undo shutdown",
        f"ip address {LOCAL_V4} 255.255.255.254",
        "ipv6 enable",
        f"ipv6 address {LOCAL_V6} 127",
        "quit",
    ):
        send(cmd)

    # eBGP to the GoBGP core, v4 + v6.
    for cmd in (
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
    ):
        send(cmd)

    send("commit")
    nc.exit_config_mode()
    print(nc.send_command('save force', read_timeout=90))
    print(nc.send_command("display ip interface brief", read_timeout=60))
    nc.disconnect()
    print("Huawei configured.")


if __name__ == "__main__":
    main()
