#!/bin/sh
# IOL reads config.txt only on its first boot; later boots read NVRAM.
set -eu
for NODE in iol ioll2; do
    [ "$(docker inspect -f '{{.State.Running}}' "clab-ultraglass-$NODE" 2>/dev/null)" = true ] || continue
    case "$NODE" in
        iol) ADDRESS=192.168.250.19 ;;
        ioll2) ADDRESS=192.168.250.20 ;;
    esac
    echo "Waiting for $NODE and saving its startup configuration..."
    ATTEMPT=0
    SAVED=false
    while [ "$ATTEMPT" -lt 30 ]; do
        OUTPUT=$(timeout 20 sshpass -p admin ssh -o ConnectTimeout=5 \
            -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
            "admin@$ADDRESS" 'write memory' 2>&1) || OUTPUT="SSH not ready: $OUTPUT"
        if printf '%s\n' "$OUTPUT" | grep -q '\[OK\]'; then
            SAVED=true
            break
        fi
        ATTEMPT=$((ATTEMPT + 1))
        sleep 5
    done
    if [ "$SAVED" != true ]; then
        printf 'Cannot save %s: %s\n' "$NODE" "$OUTPUT" >&2
        exit 1
    fi
done
