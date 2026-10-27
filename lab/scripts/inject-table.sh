#!/bin/sh
# Load the full table into the core; GoBGP then sends it to every established peer.
# Next hop 0.0.0.0 / :: makes GoBGP advertise its own link address so routes resolve.
#
# Low-RAM: set PREFIXES to cap how many prefixes are injected per family, e.g.
#   PREFIXES=50000 ./scripts/inject-table.sh
# A smaller table means less memory on the core and on each device under test.
set -eu
C=clab-ultraglass-core
N="${PREFIXES:-}"
docker exec $C gobgp global rib -a ipv4 del all 2>/dev/null || true
docker exec $C gobgp global rib -a ipv6 del all 2>/dev/null || true
docker exec $C gobgp mrt inject global --only-best --no-ipv6 --nexthop 0.0.0.0 /data/bview $N
docker exec $C gobgp mrt inject global --only-best --no-ipv4 --nexthop :: /data/bview $N
docker exec $C gobgp global rib summary -a ipv4
docker exec $C gobgp global rib summary -a ipv6
