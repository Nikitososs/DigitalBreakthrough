#!/bin/bash
set -eu

OUT="/data/omsk_oblast.osm.pbf"
SRC="/data/siberian-fed-district.osm.pbf"
URL="https://download.geofabrik.de/russia/siberian-fed-district-latest.osm.pbf"
BBOX="70.05,53.35,76.25,57.55"

if [ -s "$OUT" ]; then
  echo "OK: $OUT already exists ($(du -h "$OUT" | cut -f1))"
  exit 0
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq wget osmium-tool ca-certificates

if [ ! -s "$SRC" ]; then
  echo "Downloading Siberian Federal District PBF (~550 MB)..."
  wget -q --show-progress -O "$SRC" "$URL"
fi

echo "Extracting Omsk Oblast (bbox $BBOX)..."
osmium extract -b "$BBOX" -o "$OUT" "$SRC"
echo "Done: $(du -h "$OUT" | cut -f1)"
rm -f "$SRC"
