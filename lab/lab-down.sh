#!/bin/sh
# Stop the lab. Containers and their state are removed; built images are kept.
cd "$(dirname "$0")"
sudo containerlab destroy -t ultraglass-lab.clab.yml
