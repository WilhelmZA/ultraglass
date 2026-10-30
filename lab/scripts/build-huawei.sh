#!/bin/sh
# Add saved-disk startup support to a vrnetlab huawei_vrp appliance image.
#
#   sh scripts/build-huawei.sh                          CE12800 (existing vrnetlab image)
#   sh scripts/build-huawei.sh ne40e /path/to/hda.qcow2 NE40E V800R011 (VRP 8.180)
#
# The NE40E form first builds vrnetlab/huawei_vrp:ne40e-eveng with docker build from a
# context assembled in a temporary directory: the disk, plus the huawei_vrp launcher and
# vrnetlab library taken from the CE12800 vrnetlab image so both nodes run the same code.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
CE=vrnetlab/huawei_vrp:ce12800-V200R005C10SPC607B607
TAG=ce12800-V200R005C10SPC607B607
if [ "${1:-}" = ne40e ]; then
    DISK=${2:?usage: build-huawei.sh ne40e /path/to/hda.qcow2}
    TAG=ne40e-eveng
    CONTEXT=$(mktemp -d)
    trap 'rm -rf "$CONTEXT"; docker rm -f huawei-launcher-extract >/dev/null 2>&1 || true' EXIT
    cp "$DISK" "$CONTEXT/huawei_ne40e-eveng.qcow2"
    docker create --name huawei-launcher-extract "$CE" >/dev/null
    for file in launch.py vrnetlab.py healthcheck.py; do
        docker cp "huawei-launcher-extract:/$file" "$CONTEXT/$file"
    done
    cat >"$CONTEXT/Dockerfile" <<'EOF'
FROM ghcr.io/srl-labs/vrnetlab-base:0.3.0
ARG IMAGE=huawei_ne40e-eveng.qcow2
COPY $IMAGE* /
COPY *.py /
EXPOSE 22 80 161/udp 443 830 5000 57400 10000-10099
EOF
    docker build -t "vrnetlab/huawei_vrp:$TAG" "$CONTEXT"
fi
docker build --build-arg BASE="vrnetlab/huawei_vrp:$TAG" -t "ultraglass-lab/huawei_vrp:$TAG" "$ROOT/images/huawei"
