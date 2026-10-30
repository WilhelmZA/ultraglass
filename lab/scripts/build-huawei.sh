#!/bin/sh
# Add saved-disk startup support to the existing CE12800 appliance.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
docker build -t ultraglass-lab/huawei_vrp:ce12800-V200R005C10SPC607B607 "$ROOT/images/huawei"
