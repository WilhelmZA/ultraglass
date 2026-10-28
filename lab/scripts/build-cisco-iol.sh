#!/bin/sh
# Wrap the IOL router and switch images from the CML 2.10 free reference ISO.
set -eu
ISO="${1:?Usage: sh scripts/build-cisco-iol.sh /path/to/refplat-20260409-free.iso}"
REVISION=85445edfdf366b3d5f04942a10bb5a7d22df61a7
[ -f "$ISO" ] || { echo "Missing reference ISO: $ISO" >&2; exit 1; }
BUILD=$(mktemp -d "${TMPDIR:-/tmp/opencode}/ultraglass-iol.XXXXXX")
git clone https://github.com/srl-labs/vrnetlab.git "$BUILD/vrnetlab"
git -C "$BUILD/vrnetlab" checkout --detach "$REVISION"
# The upstream 768 MB default cannot hold the lab's dual-stack full table.
sed -i 's/-s 0 -c config.txt/-s 0 -m "${IOL_MEMORY:-4096}" -c config.txt/' "$BUILD/vrnetlab/cisco/iol/docker/entrypoint.sh"
for NAME in iol-xe-17-18-02 ioll2-xe-17-18-02; do
    isoinfo -R -i "$ISO" -x "/virl-base-images/$NAME/$NAME.tar.gz" > "$BUILD/vrnetlab/cisco/iol/$NAME.tar.gz"
    test -s "$BUILD/vrnetlab/cisco/iol/$NAME.tar.gz"
    tar -tzf "$BUILD/vrnetlab/cisco/iol/$NAME.tar.gz" >/dev/null
done
make -C "$BUILD/vrnetlab/cisco/iol" REGISTRY=ultraglass-lab/
docker image inspect ultraglass-lab/cisco_iol:17.18.02 ultraglass-lab/cisco_iol:L2-17.18.02 --format '{{.RepoTags}}'
echo "Build directory: $BUILD"
