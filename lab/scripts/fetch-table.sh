#!/bin/sh
# Download the latest RIPE RIS full-table dump into lab/data.
# Default collector rrc19 is NAPAfrica Johannesburg. Override with: COLLECTOR=rrc00
set -eu
cd "$(dirname "$0")/.."
COLLECTOR="${COLLECTOR:-rrc19}"
mkdir -p data
curl -fL --progress-bar -o "data/$COLLECTOR-bview.gz" "https://data.ris.ripe.net/$COLLECTOR/latest-bview.gz"
gunzip -fk "data/$COLLECTOR-bview.gz"
ln -sf "$COLLECTOR-bview" data/bview
ls -la data
