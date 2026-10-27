#!/bin/sh
# Build the lab images: core, the Linux routers and ultraglass from this repo.
set -eu
cd "$(dirname "$0")/.."
for i in core frr bird openbgpd; do
  docker build -t "ultraglass-lab/$i:latest" "images/$i"
done
docker build -t ultraglass-lab/ultraglass:dev ..
