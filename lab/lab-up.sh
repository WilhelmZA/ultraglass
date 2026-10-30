#!/bin/sh
# Start the lab and load the table. Safe after a reboot.
#
#   ./lab-up.sh                 whole lab (all vendors, needs the most RAM)
#   ./lab-up.sh frr             just one device: core + redis + both ultraglass + frr
#   ./lab-up.sh mikrotik        devices: frr bird openbgpd mikrotik arista vyos huawei huawei-ne40 junos iol ioll2
#   PREFIXES=50000 ./lab-up.sh frr   cap the table for low-RAM machines
#   ./lab-up.sh --image <image-reference> [device]
#                               run a published Ultraglass image instead of the
#                               local dev build (ultraglass-lab/ultraglass:dev)
#
# Images must be built (scripts/build-images.sh) and the table fetched
# (scripts/fetch-table.sh). GoBGP holds the RIB in memory, so the table is
# injected fresh on every start.
set -e
cd "$(dirname "$0")"
IMAGE=${ULTRAGLASS_IMAGE:-$(docker inspect -f '{{.Config.Image}}' clab-ultraglass-ultraglass 2>/dev/null || echo ultraglass-lab/ultraglass:dev)}
if [ "${1:-}" = "--image" ]; then
    [ -n "${2:-}" ] || { echo "--image needs an image reference" >&2; exit 1; }
    IMAGE="$2"
    shift 2
fi
DEV="${1:-}"
case " frr bird openbgpd mikrotik arista vyos huawei huawei-ne40 junos iol ioll2 " in
    *" $DEV "*) : ;;
    *) [ -z "$DEV" ] || { echo "Unknown device '$DEV'" >&2; exit 1; } ;;
esac
PYTHON=${LAB_PYTHON:-../.venv/bin/python3}
[ -x "$PYTHON" ] || PYTHON=python3
"$PYTHON" -c 'import yaml, netmiko'

# Ultraglass refuses to start without its (git-ignored) log directory.
mkdir -p configs/ultraglass/logs configs/ultraglass-text/logs

if [ ! -e data/bview ]; then
    echo "No table dump at data/bview. Run scripts/fetch-table.sh first." >&2
    exit 1
fi

# Use the image's ID, so a rebuilt dev image or a different tag both count as a change.
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "Pulling $IMAGE..."
    docker pull "$IMAGE"
fi
WANT="$(docker image inspect -f '{{.Id}}' "$IMAGE")"
# `docker restart` and a redeploy keep a container's old image, so remove any
# Ultraglass container that runs a different image. The deploy recreates it.
for C in clab-ultraglass-ultraglass clab-ultraglass-ultraglass-text; do
    HAVE="$(docker inspect -f '{{.Image}}' "$C" 2>/dev/null || true)"
    if [ -n "$HAVE" ] && [ "$HAVE" != "$WANT" ]; then
        echo "Recreating $C on $IMAGE"
        docker rm -f "$C" >/dev/null
    fi
done

NODES="core redis ultraglass ultraglass-text ${DEV:-frr bird openbgpd mikrotik arista vyos huawei huawei-ne40 junos iol ioll2}"
EXISTING=true
for N in $NODES; do
    docker inspect "clab-ultraglass-$N" >/dev/null 2>&1 || EXISTING=false
done
if [ "$EXISTING" = true ]; then
    for N in $NODES; do
        "$PYTHON" scripts/start-node.py "$N"
    done
elif [ -n "$DEV" ]; then
    case " frr bird openbgpd mikrotik arista vyos huawei huawei-ne40 junos iol ioll2 " in
        *" $DEV "*) : ;;
        *) echo "Unknown device '$DEV'. Pick one of: frr bird openbgpd mikrotik arista vyos huawei huawei-ne40 junos iol ioll2" >&2; exit 1 ;;
    esac
    echo "Starting single device: $DEV (plus core, redis, ultraglass)"
    sudo env ULTRAGLASS_IMAGE="$IMAGE" containerlab deploy -t ultraglass-lab.clab.yml --node-filter "core,redis,ultraglass,ultraglass-text,$DEV"
else
    echo "Starting the whole lab"
    sudo env ULTRAGLASS_IMAGE="$IMAGE" containerlab deploy -t ultraglass-lab.clab.yml
fi
if [ "$EXISTING" != true ]; then
    for N in $NODES; do
        "$PYTHON" scripts/start-node.py "$N"
    done
fi

echo "Waiting for the core router..."
LIMIT=$(( $(date +%s) + 60 ))
until docker exec clab-ultraglass-core gobgp global rib summary -a ipv4 >/dev/null 2>&1; do
    [ "$(date +%s)" -lt "$LIMIT" ] || { echo "Core boot timed out" >&2; exit 1; }
    sleep 2
done

# Core link addressing. ethN carries 10.250.N.0/31 + fd00:250:N::/127 (N matches the
# device subnet). Applied idempotently here so it is correct no matter how the core
# was created (a prior single-device deploy can leave it with only some interfaces).
for N in 1 2 3 4 5 6 7 8 9 10 11; do
    docker exec clab-ultraglass-core sh -c "ip addr add 10.250.$N.0/31 dev eth$N 2>/dev/null; ip addr add fd00:250:$N::/127 dev eth$N 2>/dev/null; true"
done

# Save the first-boot IOL configuration before any later restart uses NVRAM.
sh scripts/save-cisco-iol.sh

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

echo
echo "Lab up on $IMAGE. Ultraglass structured: http://127.0.0.1:8001  text: http://127.0.0.1:8002"
echo "Query a device by its name: lab-frr, lab-bird, lab-openbgpd, lab-mikrotik, lab-arista, lab-vyos, lab-huawei-vrpv8, lab-huawei-ne40, lab-junos, lab-iol, lab-ioll2"
