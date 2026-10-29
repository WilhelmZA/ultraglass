#!/bin/sh
# Download from the publisher, verify, inspect offline, then build a pinned wrapper.
set -eu

PLATFORM=${1:?Usage: build-platform.sh sonic|exos|voss}
CACHE=${PLATFORM_IMAGE_DIR:-/tmp/opencode/ultraglass-tier3-images}
REVISION=85445edfdf366b3d5f04942a10bb5a7d22df61a7
case "$PLATFORM" in
    sonic)
        FILE=sonic-vs-202505.1238524.img.gz
        DISK=sonic-vs-202505.1238524.qcow2
        URL='https://sonic-build.azurewebsites.net/api/sonic/artifacts?branchName=202505&platform=vs&buildId=1238524&target=target%2Fsonic-vs.img.gz'
        SHA256=b4225804b2098704c99e2b7c790fe6f70ebcf07fae55ded6fe63042c535c2ee8
        MD5=
        WRAPPER=sonic
        ;;
    exos)
        FILE=EXOS-VM_32.7.2.19.qcow2
        DISK=$FILE
        URL=https://akamai-ep.extremenetworks.com/Extreme_P/github-en/Virtual_EXOS/$FILE
        SHA256=873b789bd82cf370bf825435dbda49cb281ce0989ef794e47883f86f95344541
        MD5=eba580a2e18d2a9cc972c9ece8917ea8
        WRAPPER=extreme/exos
        ;;
    voss)
        FILE=FEGNS3.9.4.0.0.qcow2
        DISK=$FILE
        URL=https://akamai-ep.extremenetworks.com/Extreme_P/github-en/Virtual_VOSS/$FILE
        SHA256=3063c4ccbbdedf6237e9e5827cebb66efaa151c4b032f38c39000b29d6e65b1c
        MD5=341aef71e2dbb976e6fa6369b363789e
        WRAPPER=extreme/voss
        ;;
    *) echo "Unknown platform: $PLATFORM" >&2; exit 1 ;;
esac

umask 077
mkdir -p "$CACHE"
CACHE=$(cd "$CACHE" && pwd)
# Refuse a partial file unless its checksum matches the publisher's reference.
if [ ! -f "$CACHE/$FILE" ]; then
    if [ ! -f "$CACHE/$FILE.part" ]; then
        curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' \
            --max-time 1800 --output "$CACHE/$FILE.part" "$URL"
    fi
    CHECK=$FILE.part
else
    CHECK=$FILE
fi
if [ -n "$SHA256" ]; then
    (cd "$CACHE" && printf '%s  %s\n' "$SHA256" "$CHECK" | sha256sum --check)
fi
if [ -n "$MD5" ]; then
    (cd "$CACHE" && printf '%s  %s\n' "$MD5" "$CHECK" | md5sum --check)
fi
if [ "$CHECK" != "$FILE" ]; then mv "$CACHE/$CHECK" "$CACHE/$FILE"; fi

isolated() {
    timeout 300 bwrap --unshare-all --die-with-parent --cap-drop ALL \
        --ro-bind /usr /usr --ro-bind /lib /lib --ro-bind /lib64 /lib64 \
        --proc /proc --dev /dev --tmpfs /tmp --ro-bind "$CACHE" /images \
        --clearenv --setenv PATH /usr/bin:/bin "$@"
}
if [ "$FILE" != "$DISK" ]; then
    isolated /usr/bin/gzip -dc "/images/$FILE" > "$CACHE/$DISK.part"
    mv "$CACHE/$DISK.part" "$CACHE/$DISK"
fi
isolated /usr/bin/qemu-img info -f qcow2 --output=json "/images/$DISK" > "$CACHE/$PLATFORM-info.json"
python3 - "$CACHE/$PLATFORM-info.json" <<'PY'
import json, sys
info = json.load(open(sys.argv[1]))
assert not info.get('backing-filename'), 'Unexpected backing file'
assert not info.get('format-specific', {}).get('data', {}).get('data-file'), 'Unexpected external data file'
assert info['virtual-size'] <= 64 * 1024**3, 'Unexpected virtual disk size'
PY
isolated /usr/bin/qemu-img check -f qcow2 --output=json "/images/$DISK" > "$CACHE/$PLATFORM-check.json"
(cd "$CACHE" && sha256sum "$FILE" "$DISK") > "$CACHE/$PLATFORM-sha256.txt"

BUILD=$(mktemp -d "${TMPDIR:-/tmp/opencode}/ultraglass-$PLATFORM.XXXXXX")
git -C "$BUILD" init --quiet
git -C "$BUILD" remote add origin https://github.com/srl-labs/vrnetlab.git
git -C "$BUILD" fetch --quiet --depth 1 origin "$REVISION"
git -C "$BUILD" checkout --quiet --detach FETCH_HEAD
if [ "$PLATFORM" = exos ]; then
    # The preceding wait_write_config already consumes '#'. Waiting for it again
    # can stall first-boot password setup until the next unsolicited console line.
    python3 - "$BUILD/$WRAPPER/docker/launch.py" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
text = p.read_text()
old_read = '                res = self.tn.read_until(wait.encode(), timeout=30)'
assert text.count(old_read) == 1
text = text.replace(old_read, '                _, match, res = self.tn.expect([re.escape(cmd.encode()) + rb"[\\s\\S]*" + re.escape(wait.encode())], 30)\n                if match is None:\n                    raise TimeoutError(f"Missing completion prompt for {cmd}")')
old_mgmt = '        self.wait_write_config(cmd="unconfigure vlan Mgmt ipaddress")'
assert text.count(old_mgmt) == 1
text = text.replace(old_mgmt, '        self.wait_write_config(cmd="disable dhcp vlan Mgmt")\n' + old_mgmt)
old = 'self.wait_write(cmd="configure account admin password", wait="#")'
assert text.count(old) == 1
p.write_text(text.replace(old, 'self.wait_write(cmd="configure account admin password", wait=None)'))
PY
fi
cp --reflink=auto "$CACHE/$DISK" "$BUILD/$WRAPPER/"
make -C "$BUILD/$WRAPPER" REGISTRY=ultraglass-lab/ IMAGE="$DISK" docker-build
echo "Build directory: $BUILD"
