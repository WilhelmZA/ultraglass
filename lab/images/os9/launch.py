#!/usr/bin/env python3
"""Boot the OS9 emulator and configure its lab management interface."""
import argparse
import logging
import os
from pathlib import Path
import re
import signal
import sys
import time

import vrnetlab


class OS9VM(vrnetlab.VM):
    prompt = rb"(?m)^[\w.-]+(?:\([^)]+\))?[#>]"

    def __init__(self, args):
        super().__init__(
            args.username, args.password, disk_image="/os9.qcow2",
            ram=1024, cpu="qemu32", driveif="ide", min_dp_nics=5,
            provision_pci_bus=False,
        )
        self.qemu_args[0] = "qemu-system-i386"
        self.hostname = args.hostname
        self.conn_mode = args.connection_mode
        self.num_nics = 5
        self.nic_type = "e1000"
        self.bootstrap_failed = False
        self.qemu_args.extend(["-cdrom", "/os9.iso", "-boot", "d"])

    def gen_dummy_nics(self):
        # Keep management first in the emulator's PCI interface enumeration.
        return [re.sub(r",bus=pci\.\d+,addr=0x[0-9a-f]+", "", arg)
                for arg in super().gen_dummy_nics()]

    def command(self, command):
        time.sleep(0.5)
        self.tn.write(command.encode() + b"\r")
        _, match, output = self.tn.expect([self.prompt], 120)
        if not match or re.search(rb"%\s*(?:Error|Invalid|Incomplete|Ambiguous)", output, re.I):
            raise RuntimeError(f"OS9 command failed: {command}\n{output.decode(errors='replace')}")

    def bootstrap_spin(self):
        if self.bootstrap_failed:
            return
        _, match, _ = self.tn.expect([self.prompt], 1)
        if not match:
            self.spins += 1
            if self.spins > 900:
                raise RuntimeError("OS9 console did not reach its prompt")
            return
        commands = [
            "enable", "terminal length 0", "configure terminal", "no logging console",
            f"hostname {self.hostname}",
            f"username {self.username} password 0 {self.password} privilege 15",
            "ip ssh server enable", "interface managementethernet 0/0",
            "ip address 10.0.0.15/24", "no shutdown", "exit",
            "management route 0.0.0.0/0 10.0.0.2",
        ]
        startup = Path("/config/startup.cfg")
        if startup.exists():
            commands.extend(line.strip() for line in startup.read_text().splitlines()
                            if line.strip() and not line.lstrip().startswith("!"))
        commands.extend(["end", "write memory"])
        try:
            for command in commands:
                self.command(command)
        except RuntimeError:
            # Keep the console available for diagnosis, but do not report healthy.
            self.bootstrap_failed = True
            self.tn.close()
            self.logger.exception("OS9 startup configuration failed")
            return
        self.tn.close()
        self.running = True
        self.logger.info("OS9 startup configuration complete")


class OS9(vrnetlab.VR):
    def __init__(self, args):
        super().__init__(args.username, args.password)
        self.vms = [OS9VM(args)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hostname", default=os.getenv("HOSTNAME", "os9"))
    parser.add_argument("--username", default=os.getenv("USERNAME", "admin"))
    parser.add_argument("--password", default=os.getenv("PASSWORD", "Lab-Router9"))
    parser.add_argument("--connection-mode", default=os.getenv("CONNECTION_MODE", "tc"))
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.trace else logging.INFO)
    logging.Logger.trace = logging.Logger.debug
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    OS9(args).start()
