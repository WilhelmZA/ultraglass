#!/bin/sh
# Build the RouterOS lab appliance from a CHR disk.
set -eu
DISK=${1:?Usage: build-routeros6.sh /path/to/chr.vmdk}
REVISION=85445edfdf366b3d5f04942a10bb5a7d22df61a7
BUILD=$(mktemp -d /tmp/opencode/ultraglass-routeros6-build.XXXXXX)
git -C "$BUILD" init --quiet
git -C "$BUILD" remote add origin https://github.com/srl-labs/vrnetlab.git
git -C "$BUILD" fetch --quiet --depth 1 origin "$REVISION"
git -C "$BUILD" checkout --quiet --detach FETCH_HEAD
cp --reflink=auto "$DISK" "$BUILD/mikrotik/routeros/chr-6.49.19.vmdk"
make -C "$BUILD/mikrotik/routeros" REGISTRY=ultraglass-lab/ IMAGE=chr-6.49.19.vmdk docker-build
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
docker build --build-arg BASE=ultraglass-lab/mikrotik_routeros:6.49.19 \
    -t ultraglass-lab/mikrotik_routeros:6.49.19 "$ROOT/images/mikrotik"
echo "Build directory: $BUILD"
