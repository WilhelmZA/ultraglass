#!/bin/sh
# Build the TiMOS 15.0.R3 lab image.
set -eu
DISK=${1:?Usage: build-timos.sh /path/to/timos.qcow2}
REVISION=85445edfdf366b3d5f04942a10bb5a7d22df61a7
SHA256=62f457df48f1d35d68b421c33d864e62df0300cfc15c42f5efe722e5e2895d1c
printf '%s  %s\n' "$SHA256" "$DISK" | sha256sum --check
BUILD=$(mktemp -d /tmp/opencode/ultraglass-timos-build.XXXXXX)
git -C "$BUILD" init --quiet
git -C "$BUILD" remote add origin https://github.com/srl-labs/vrnetlab.git
git -C "$BUILD" fetch --quiet --depth 1 origin "$REVISION"
git -C "$BUILD" checkout --quiet --detach FETCH_HEAD
cp --reflink=auto "$DISK" "$BUILD/nokia/sros/sros-vm-15.0.R3.qcow2"
make -C "$BUILD/nokia/sros" REGISTRY=ultraglass-lab/ IMAGE=sros-vm-15.0.R3.qcow2 docker-build
echo "Build directory: $BUILD"
