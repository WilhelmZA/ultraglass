#!/bin/sh
# Run one additional platform at a time without loading the core's full table.
set -eu
cd "$(dirname "$0")"
ACTION=${1:-status}
NODE=${2:-}
PREFIX=clab-ultraglass-platforms

case "$ACTION" in
    status)
        docker ps -a --filter label=containerlab=ultraglass-platforms \
            --format 'table {{.Names}}\t{{.Status}}'
        exit 0 ;;
    stop)
        for N in sonic exos voss probe; do
            if [ "$(docker inspect -f '{{.State.Running}}' "$PREFIX-$N" 2>/dev/null || true)" = true ]; then
                docker stop "$PREFIX-$N"
            fi
        done
        exit 0 ;;
    start) ;;
    *) echo "Usage: sh platform.sh start sonic|exos|voss | stop | status" >&2; exit 1 ;;
esac

case "$NODE" in
    sonic) IMAGE=ultraglass-lab/sonic_sonic-vs:202505.1238524; LIMIT_MB=5120 ;;
    exos) IMAGE=ultraglass-lab/extreme_exos:32.7.2.19; LIMIT_MB=2048 ;;
    voss) IMAGE=ultraglass-lab/extreme_voss:9.4.0.0; LIMIT_MB=3072 ;;
    *) echo "Pick sonic, exos or voss" >&2; exit 1 ;;
esac
docker image inspect "$IMAGE" >/dev/null 2>&1 || {
    echo "Build the image first: sh scripts/build-platform.sh $NODE" >&2
    exit 1
}

# Stop only the optional platforms. Keep the existing full-table lab untouched.
for N in sonic exos voss; do
    if [ "$N" != "$NODE" ] && [ "$(docker inspect -f '{{.State.Running}}' "$PREFIX-$N" 2>/dev/null || true)" = true ]; then
        docker stop "$PREFIX-$N"
    fi
done
if [ "$(docker inspect -f '{{.State.Running}}' "$PREFIX-$NODE" 2>/dev/null || true)" = true ]; then
    echo "$NODE is already running"
    exit 0
fi
# Reserve 12 GiB for the host, existing lab and other applications.
AVAILABLE_MB=$(awk '/^MemAvailable:/ {print int($2 / 1024)}' /proc/meminfo)
REQUIRED_MB=$((LIMIT_MB + 128 + 12288))
if [ "$AVAILABLE_MB" -lt "$REQUIRED_MB" ]; then
    echo "Need $REQUIRED_MB MiB available; have $AVAILABLE_MB MiB. Leave $NODE stopped." >&2
    exit 1
fi

# Destroy the previous two-node topology before replacing its file. Destroy uses
# the file's node list, so overwriting it first could leave the previous VM behind.
if [ -f data/platforms/active.clab.yml ]; then
    sudo -n containerlab destroy --keep-mgmt-net -t data/platforms/active.clab.yml
fi
# Containerlab 0.82 rejects --node-filter on an existing lab. Render a two-node
# topology instead, preserving the management network shared with the main lab.
mkdir -p data/platforms
python3 - "$NODE" <<'PY'
import sys
from pathlib import Path
import yaml

node = sys.argv[1]
topology = yaml.safe_load(Path('ultraglass-platforms.clab.yml').read_text())
nodes = topology['topology']['nodes']
topology['topology']['nodes'] = {name: nodes[name] for name in ('probe', node)}
for definition in topology['topology']['nodes'].values():
    definition['binds'] = [
        str(Path(bind.split(':', 1)[0]).resolve()) + ':' + bind.split(':', 1)[1]
        for bind in definition.get('binds', [])
    ]
topology['topology']['links'] = [
    link for link in topology['topology']['links']
    if any(endpoint.startswith(node + ':') for endpoint in link['endpoints'])
]
number = {'sonic': 1, 'exos': 2, 'voss': 3}[node]
address = '10.251.3.2/30' if node == 'voss' else f'10.251.{number}.0/31'
nodes['probe']['exec'] = [f'ip address replace {address} dev eth{number}']
Path('data/platforms/active.clab.yml').write_text(yaml.safe_dump(topology, sort_keys=False))
PY
sudo -n containerlab deploy -t data/platforms/active.clab.yml
echo "Started $NODE without BGP peers. Stop it with: sh platform.sh stop"
