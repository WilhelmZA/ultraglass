#!/bin/sh
# Build the IOSv 15.9(3)M6 lab image.
set -eu
DISK=${1:?Usage: build-iosv.sh /path/to/iosv.qcow2}
REVISION=85445edfdf366b3d5f04942a10bb5a7d22df61a7
SHA256=3a1aac6ea18d641206a8ccb511122b3ae25b71f139c90b2a9a3d02350ff8d857
printf '%s  %s\n' "$SHA256" "$DISK" | sha256sum --check
BUILD=$(mktemp -d /tmp/opencode/ultraglass-iosv-build.XXXXXX)
git -C "$BUILD" init --quiet
git -C "$BUILD" remote add origin https://github.com/srl-labs/vrnetlab.git
git -C "$BUILD" fetch --quiet --depth 1 origin "$REVISION"
git -C "$BUILD" checkout --quiet --detach FETCH_HEAD
cp --reflink=auto "$DISK" "$BUILD/cisco/vios/cisco_vios-15.9.3M6.qcow2"
make -C "$BUILD/cisco/vios" REGISTRY=ultraglass-lab/ IMAGE=cisco_vios-15.9.3M6.qcow2 docker-build
echo "Build directory: $BUILD"
