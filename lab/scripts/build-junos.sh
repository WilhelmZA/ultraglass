#!/bin/sh
# Build vJunos-router with upstream's AMD SVM patch, preserving the vendor disk.
set -eu

IMAGE="${1:-$HOME/Downloads/vJunos-router-26.2R1.7.qcow2}"
REVISION=85445edfdf366b3d5f04942a10bb5a7d22df61a7
if [ ! -f "$IMAGE" ]; then
    echo "Missing vJunos-router QCOW2: $IMAGE" >&2
    exit 1
fi
case "$(basename "$IMAGE")" in
    vJunos-router-*.qcow2) ;;
    *) echo "Expected vJunos-router-<version>.qcow2" >&2; exit 1 ;;
esac

BUILD=$(mktemp -d "${TMPDIR:-/tmp/opencode}/ultraglass-vjunos.XXXXXX")
git clone https://github.com/srl-labs/vrnetlab.git "$BUILD/vrnetlab"
git -C "$BUILD/vrnetlab" checkout --detach "$REVISION"
cp --reflink=auto "$IMAGE" "$BUILD/vrnetlab/juniper/vjunosrouter/"
# The Makefile patches the copy with vjunos-amd-enable, then builds the image.
make -C "$BUILD/vrnetlab/juniper/vjunosrouter" REGISTRY=ultraglass-lab/
echo "Build directory: $BUILD"
