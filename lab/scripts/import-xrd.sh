#!/bin/sh
# Import the XRd container archive for the lab.
set -eu
PAYLOAD=${1:?Usage: import-xrd.sh /path/to/image.tgz}
SHA256=31946f9c5f80723617aabba9d66bde39b3944caac907f3ba590dcadc23667b64
IMAGE_ID=sha256:f160dc83ee7e6ef3c9e66254d32237c8d62052f91539da0defc38ddfcc2f36af
printf '%s  %s\n' "$SHA256" "$PAYLOAD" | sha256sum --check
docker load --input "$PAYLOAD"
[ "$(docker image inspect ios-xr/xrd-control-plane:24.2.11 --format '{{.Id}}')" = "$IMAGE_ID" ]
docker tag "$IMAGE_ID" ultraglass-lab/cisco_xrd:24.2.11
