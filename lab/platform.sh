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
        for N in sonic exos voss xrd iosv nexus timos probe; do
            if [ "$(docker inspect -f '{{.State.Running}}' "$PREFIX-$N" 2>/dev/null || true)" = true ]; then
                docker stop "$PREFIX-$N"
            fi
        done
        exit 0 ;;
    start) ;;
    *) echo "Usage: sh platform.sh start sonic|exos|voss|xrd|iosv|nexus|timos | stop | status" >&2; exit 1 ;;
esac

case "$NODE" in
    sonic) IMAGE=ultraglass-lab/sonic_sonic-vs:202505.1238524; LIMIT_MB=5120 ;;
    exos) IMAGE=ultraglass-lab/extreme_exos:32.7.2.19; LIMIT_MB=2048 ;;
    voss) IMAGE=ultraglass-lab/extreme_voss:9.4.0.0; LIMIT_MB=3072 ;;
    xrd) IMAGE=ultraglass-lab/cisco_xrd:24.2.11; LIMIT_MB=4096 ;;
    iosv) IMAGE=ultraglass-lab/cisco_vios:15.9.3M6; LIMIT_MB=2048 ;;
    nexus) IMAGE=ultraglass-lab/cisco_n9kv:9300-lite-10.4.8.M; LIMIT_MB=10240 ;;
    timos) IMAGE=ultraglass-lab/nokia_sros:15.0.R3; LIMIT_MB=10240 ;;
    *) echo "Pick sonic, exos, voss, xrd, iosv, nexus or timos" >&2; exit 1 ;;
esac
docker image inspect "$IMAGE" >/dev/null 2>&1 || {
    if [ "$NODE" = xrd ]; then
        echo "Import the image first: sh scripts/import-xrd.sh /path/to/image.tgz" >&2
    elif [ "$NODE" = iosv ]; then
        echo "Build the image first: sh scripts/build-iosv.sh /path/to/iosv.qcow2" >&2
    elif [ "$NODE" = nexus ]; then
        echo "Build the image first: sh scripts/build-nexus.sh /path/to/nexus.qcow2" >&2
    elif [ "$NODE" = timos ]; then
        echo "Build the image first: sh scripts/build-timos.sh /path/to/timos.qcow2" >&2
    else
        echo "Build the image first: sh scripts/build-platform.sh $NODE" >&2
    fi
    exit 1
}
if [ "$NODE" = xrd ]; then
    EXPECTED=sha256:f160dc83ee7e6ef3c9e66254d32237c8d62052f91539da0defc38ddfcc2f36af
    [ "$(docker image inspect "$IMAGE" --format '{{.Id}}')" = "$EXPECTED" ] || {
        echo "XRd image does not match the configured image ID." >&2
        exit 1
    }
fi
case "$NODE" in
    xrd|iosv|nexus|timos) docker image inspect ultraglass-lab/core:latest >/dev/null ;;
esac
if [ "$NODE" = timos ] && [ ! -s data/platforms/timos.license ]; then
    echo "Place the TiMOS license at lab/data/platforms/timos.license first." >&2
    exit 1
fi

# Stop only the optional platforms. Keep the existing full-table lab untouched.
for N in sonic exos voss xrd iosv nexus timos; do
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
REQUIRED_MB=$((LIMIT_MB + 256 + 12288))
if [ "$AVAILABLE_MB" -lt "$REQUIRED_MB" ]; then
    echo "Need $REQUIRED_MB MiB available; have $AVAILABLE_MB MiB. Leave $NODE stopped." >&2
    exit 1
fi

# Destroy the previous two-node topology before replacing its file. Destroy uses
# the file's node list, so overwriting it first could leave the previous VM behind.
if [ -f data/platforms/active.clab.yml ]; then
    sudo -n containerlab destroy --keep-mgmt-net -t data/platforms/active.clab.yml
fi
# Remove containers left by a run whose rendered topology is gone, for example a run
# from another checkout. Deploy cannot reconcile a stopped appliance and fails.
STALE=$(docker ps -aq --filter label=containerlab=ultraglass-platforms)
if [ -n "$STALE" ]; then
    # shellcheck disable=SC2086
    docker rm -f $STALE >/dev/null
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
if node in ('xrd', 'iosv', 'nexus', 'timos'):
    nodes['probe'].update(
        image='ultraglass-lab/core:latest', memory='256MiB',
        entrypoint='gobgpd', cmd='-f /etc/gobgp/gobgpd.toml -t toml',
        binds=[f'configs/{node}/gobgpd.toml:/etc/gobgp/gobgpd.toml:ro'],
    )
for definition in topology['topology']['nodes'].values():
    if 'startup-config' in definition:
        definition['startup-config'] = str(Path(definition['startup-config']).resolve())
    if 'license' in definition:
        definition['license'] = str(Path(definition['license']).resolve())
    definition['binds'] = [
        str(Path(bind.split(':', 1)[0]).resolve()) + ':' + bind.split(':', 1)[1]
        for bind in definition.get('binds', [])
    ]
topology['topology']['links'] = [
    link for link in topology['topology']['links']
    if any(endpoint.startswith(node + ':') for endpoint in link['endpoints'])
]
number = {'sonic': 1, 'exos': 2, 'voss': 3, 'xrd': 4, 'iosv': 5, 'nexus': 6, 'timos': 7}[node]
address = '10.251.3.2/30' if node == 'voss' else f'10.251.{number}.0/31'
nodes['probe']['exec'] = [f'ip address replace {address} dev eth{number}']
if node in ('xrd', 'iosv', 'nexus', 'timos'):
    nodes['probe']['exec'] += [
        f'ip address replace fd00:251:{number}::/127 dev eth{number}',
        'ip address replace 1.1.1.1/32 dev lo',
        'ip address replace 2606:4700::1111/128 dev lo',
        f'gobgp global rib add 1.1.1.0/24 nexthop 10.251.{number}.0 aspath 13335 community 37195:302',
        f'gobgp global rib add -a ipv6 2606:4700::/44 nexthop fd00:251:{number}:: aspath 13335 community 37195:302',
        f'gobgp neighbor 10.251.{number}.1 disable',
        f'gobgp neighbor fd00:251:{number}::1 disable',
    ]
Path('data/platforms/active.clab.yml').write_text(yaml.safe_dump(topology, sort_keys=False))
PY
sudo -n containerlab deploy -t data/platforms/active.clab.yml
echo "Started $NODE. Fixture BGP peers start disabled. Stop with: sh platform.sh stop"
