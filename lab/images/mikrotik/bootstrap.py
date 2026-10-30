"""RouterOS console bootstrap for both fresh and saved CHR disks."""

import hashlib
import os
from pathlib import Path
import re
import time

import vrnetlab


def stable_mac(last_octet=None):
    identity = f"ultraglass:{os.environ['HOSTNAME']}:{last_octet}"
    suffix = hashlib.sha256(identity.encode()).digest()[:5]
    return "02:" + ":".join(f"{byte:02x}" for byte in suffix)


vrnetlab.gen_mac = stable_mac
Path("/health").write_text("1 starting")


def bootstrap_spin(self):
    if not hasattr(self, "login_started"):
        self.login_started = time.monotonic()
        self.login_attempt = 0
        self.fresh_disk = False
    if time.monotonic() - self.login_started > 180:
        raise RuntimeError("RouterOS console login timed out")
    index, match, output = self.tn.expect(
        [
            rb"(?i)[\w.-]+ Login: ?",
            rb"Password: ?",
            rb"Do you want to see the software license\? \[Y/n\]: ?",
            rb"repeat new password>",
            rb"new password>",
            rb"\[[^\r\n]+@[^\r\n]+\] > ?",
            rb"Please press .+Enter.+continue",
        ],
        1,
    )
    if not match:
        return
    if index == 0:
        self.login_attempt += 1
        if self.login_attempt > 2:
            raise RuntimeError("RouterOS rejected configured and factory credentials")
        username = self.username if self.login_attempt == 1 else "admin"
        self.tn.write((username + "+ct\r").encode())
    elif index == 1:
        self.fresh_disk = self.login_attempt == 2
        self.tn.write((("" if self.fresh_disk else self.password) + "\r").encode())
    elif index == 2:
        self.tn.write(b"n\r")
    elif index in (3, 4):
        self.fresh_disk = True
        self.tn.write((self.password + "\r").encode())
    elif index == 6:
        self.tn.write(b"\r")
    else:
        # Older wrappers changed the NIC MAC on every boot. RouterOS then creates
        # new interfaces and leaves the saved IP addresses on missing interfaces.
        commands = [
            ":while ([:len [/interface ethernet find]] < 2) do={ :delay 1s }",
            "/interface ethernet set [find default-name=ether1] name=ether1",
            "/interface ethernet set [find default-name=ether2] name=ether2",
            '/ip address set [find address="172.31.255.30/30"] interface=ether1',
        ]
        config = Path("/ftpboot/config.auto.rsc")
        if config.exists():
            for family, address in re.findall(
                r"/(ip|ipv6) address add address=(\S+) interface=ether2", config.read_text()
            ):
                commands.append(
                    f'/{family} address set [find address="{address}"] interface=ether2'
                )
        for command in commands if not self.fresh_disk else []:
            # RouterOS 6 redraws the prompt for every echoed character. Wait for
            # command completion instead of mistaking an echoed prompt for it.
            self.tn.write((command + '; :put ("LAB_BOOTSTRAP_" . "DONE")\r').encode())
            _, ready, result = self.tn.expect([b"LAB_BOOTSTRAP_DONE"], 120)
            if not ready or any(
                error in result for error in (b"failure:", b"syntax error", b"no such item")
            ):
                raise RuntimeError(f"RouterOS interface repair failed: {command}: {result!r}")
        if self.fresh_disk:
            self.bootstrap_config()
            if os.path.exists("/ftpboot/config.auto.rsc"):
                self.push_ftp_config()
        self.tn.close()
        self.running = True
        self.logger.info("RouterOS console ready; saved configuration preserved")
