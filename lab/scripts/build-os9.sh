#!/bin/sh
# Build the OS9 emulator container from an installation ISO.
set -eu
ISO=${1:?Usage: build-os9.sh /path/to/ftos.iso}
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
BUILD=$(mktemp -d /tmp/opencode/ultraglass-os9-build.XXXXXX)
cp "$ROOT/images/os9/Dockerfile" "$ROOT/images/os9/launch.py" "$BUILD/"
cp --reflink=auto "$ISO" "$BUILD/os9.iso"
docker build -t ultraglass-lab/dell_os9:9.13.0.0 "$BUILD"
echo "Build directory: $BUILD"
