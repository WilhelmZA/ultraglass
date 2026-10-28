#!/bin/sh
# Start the lab and load the table. Safe after a reboot.
#
#   ./lab-up.sh                 whole lab (all vendors, needs the most RAM)
#   ./lab-up.sh frr             just one device: core + redis + ultraglass + frr
#   ./lab-up.sh mikrotik        devices: frr bird openbgpd mikrotik arista vyos huawei
#   PREFIXES=50000 ./lab-up.sh frr   cap the table for low-RAM machines
#
# Images must be built (scripts/build-images.sh) and the table fetched
# (scripts/fetch-table.sh). GoBGP holds the RIB in memory, so the table is
# injected fresh on every start.
set -e
cd "$(dirname "$0")"
DEV="${1:-}"

if [ ! -e data/bview ]; then
    echo "No table dump at data/bview. Run scripts/fetch-table.sh first." >&2
    exit 1
fi

if [ -n "$DEV" ]; then
    case " frr bird openbgpd mikrotik arista vyos huawei " in
        *" $DEV "*) : ;;
        *) echo "Unknown device '$DEV'. Pick one of: frr bird openbgpd mikrotik arista vyos huawei" >&2; exit 1 ;;
    esac
    echo "Starting single device: $DEV (plus core, redis, ultraglass)"
    sudo containerlab deploy -t ultraglass-lab.clab.yml --node-filter "core,redis,ultraglass,$DEV"
else
    echo "Starting the whole lab"
    sudo containerlab deploy -t ultraglass-lab.clab.yml
fi

echo "Waiting for the core router..."
until docker exec clab-ultraglass-core gobgp global rib summary -a ipv4 >/dev/null 2>&1; do sleep 2; done

# Core link addressing. ethN carries 10.250.N.0/31 + fd00:250:N::/127 (N matches the
# device subnet). Applied idempotently here so it is correct no matter how the core
# was created (a prior single-device deploy can leave it with only some interfaces).
for N in 1 2 3 4 5 7 8; do
    docker exec clab-ultraglass-core sh -c "ip addr add 10.250.$N.0/31 dev eth$N 2>/dev/null; ip addr add fd00:250:$N::/127 dev eth$N 2>/dev/null; true"
done

# MikroTik is slow to boot and sometimes applies its config only partially.
if [ -z "$DEV" ] || [ "$DEV" = mikrotik ]; then
    if docker inspect clab-ultraglass-mikrotik >/dev/null 2>&1; then
        echo "Waiting for MikroTik to finish booting..."
        until [ "$(docker inspect -f '{{.State.Health.Status}}' clab-ultraglass-mikrotik 2>/dev/null)" = healthy ]; do sleep 5; done
        MT="sshpass -p admin ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null admin@192.168.250.14"
        if ! $MT '/ip/address/print' 2>/dev/null | grep -q 10.250.4.1; then
            echo "Re-applying MikroTik config..."
            $MT '/import file-name=config.auto.rsc' 2>/dev/null || true
        fi
    fi
fi

./scripts/inject-table.sh

# Arista cEOS defaults to a per-neighbor route limit and tears the session to
# Idle(MaxPath) under a full table. maximum-routes 0 is in the startup config but
# only takes after a clean clear, so force it here when Arista is running.
if docker inspect clab-ultraglass-arista >/dev/null 2>&1; then
    echo "Lifting Arista route limit..."
    docker exec clab-ultraglass-arista Cli -p 15 -c "$(printf 'configure\nrouter bgp 65007\nneighbor 10.250.7.0 maximum-routes 0\nneighbor fd00:250:7:: maximum-routes 0\nend')" >/dev/null 2>&1 || true
    docker exec clab-ultraglass-arista Cli -p 15 -c 'clear ip bgp 10.250.7.0' >/dev/null 2>&1 || true
    docker exec clab-ultraglass-arista Cli -p 15 -c 'clear ipv6 bgp fd00:250:7::' >/dev/null 2>&1 || true
fi

# Huawei CE12800: vrnetlab only bootstraps mgmt/SSH, so the data port and eBGP
# are applied after the VM is healthy. The core caps what it sends this peer
# (gobgpd.toml) because the slow emulated switch cannot hold a full table.
if docker inspect clab-ultraglass-huawei >/dev/null 2>&1; then
    echo "Waiting for Huawei to finish booting..."
    until [ "$(docker inspect -f '{{.State.Health.Status}}' clab-ultraglass-huawei 2>/dev/null)" = healthy ]; do sleep 5; done
    echo "Configuring Huawei data port and eBGP..."
    HWPY=python3
    command -v netmiko >/dev/null 2>&1 || python3 -c 'import netmiko' 2>/dev/null || HWPY=../.venv/bin/python3
    "$HWPY" scripts/configure-huawei.py || echo "  (configure-huawei.py needs netmiko: pip install netmiko)"
fi

echo
echo "Lab up. Ultraglass UI: http://127.0.0.1:8001"
echo "Query a device by its name: lab-frr, lab-bird, lab-openbgpd, lab-mikrotik, lab-arista, lab-vyos, lab-huawei"
