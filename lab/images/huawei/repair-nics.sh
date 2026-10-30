#!/bin/sh
# Bind emulator interfaces to PCI slots instead of changing VM MAC addresses.
set -eu
RULES=/etc/udev/rules.d/70-persistent-net.rules
[ -e "$RULES.before-lab-repair" ] || cp -p "$RULES" "$RULES.before-lab-repair"
cat > "$RULES" <<'EOF'
SUBSYSTEM=="net", ACTION=="add", KERNELS=="0000:00:03.0", NAME="eth0"
SUBSYSTEM=="net", ACTION=="add", KERNELS=="0000:00:04.0", NAME="eth1"
SUBSYSTEM=="net", ACTION=="add", KERNELS=="0000:01:02.0", NAME="eth2"
EOF
sync
