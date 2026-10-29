#!/bin/sh
# Build the Nexus 9300v Lite 10.4.8.M lab image.
set -eu
DISK=${1:?Usage: build-nexus.sh /path/to/nexus.qcow2}
REVISION=85445edfdf366b3d5f04942a10bb5a7d22df61a7
SHA256=bf1c88c26f40ba5e8366d6ae6417462c78d1fb7627a07a3bbc5cfec96eea6caa
printf '%s  %s\n' "$SHA256" "$DISK" | sha256sum --check
BUILD=$(mktemp -d /tmp/opencode/ultraglass-nexus-build.XXXXXX)
git -C "$BUILD" init --quiet
git -C "$BUILD" remote add origin https://github.com/srl-labs/vrnetlab.git
git -C "$BUILD" fetch --quiet --depth 1 origin "$REVISION"
git -C "$BUILD" checkout --quiet --detach FETCH_HEAD
cp --reflink=auto "$DISK" "$BUILD/cisco/n9kv/n9kv-9300-lite-10.4.8.M.qcow2"
make -C "$BUILD/cisco/n9kv" REGISTRY=ultraglass-lab/ IMAGE=n9kv-9300-lite-10.4.8.M.qcow2 docker-build
echo "Build directory: $BUILD"
