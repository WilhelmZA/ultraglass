#!/usr/bin/env python3
"""Add saved-disk startup support to the CE12800 wrapper."""

import base64
from pathlib import Path
import sys


def patch(launcher):
    source = launcher.read_text()
    source = source.replace(
        'if not disk_image and re.search(".qcow2$", e):',
        'if not disk_image and e.endswith(".qcow2") and "-overlay" not in e:',
    )
    source = source.replace('if "huawei_ne40e" in e:', 'if "ne40e" in e.lower():')
    source = source.replace('if "huawei_ce12800" in e:', 'if "ce12800" in e.lower():')
    source = source.replace(
        'self.tn.expect([b"<HUAWEI>"], 1)', 'self.tn.expect([rb"<[\\w.-]+>"], 1)'
    )
    marker = "        # If prompt matched (via expect OR drained into full_output) do config"
    saved = """        # Preserve the committed configuration on subsequent boots.
        if ("<" + self.hostname + ">").encode() in full_output:
            self.tn.close()
            self.running = True
            return

"""
    if saved not in source:
        source = source.replace(marker, saved + marker)
    payload = base64.b64encode(Path(__file__).with_name("repair-nics.sh").read_bytes()).decode()
    recovery = f"""        if b"root@debian:/opt/svrp#" in full_output and not getattr(self, "lab_nics_repaired", False):
            self.lab_nics_repaired = True
            self.wait_write("echo {payload} | base64 -d | sh", wait=None)
            self.wait_write("reboot", wait="# ")
            return

"""
    if "self.lab_nics_repaired = True" not in source:
        source = source.replace(marker, recovery + marker)
    required = (
        '"-overlay" not in e',
        'if "ce12800" in e.lower():',
        "self.lab_nics_repaired = True",
        "Preserve the committed configuration",
    )
    if not all(fragment in source for fragment in required):
        raise RuntimeError("Unsupported Huawei launcher; startup patch did not apply")
    compile(source, str(launcher), "exec")
    launcher.write_text(source)


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
