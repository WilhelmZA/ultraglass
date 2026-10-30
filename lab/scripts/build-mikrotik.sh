#!/bin/sh
# Add saved-disk login support to the existing RouterOS appliance.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
docker build -t ultraglass-lab/mikrotik_routeros:7.16.2 "$ROOT/images/mikrotik"
