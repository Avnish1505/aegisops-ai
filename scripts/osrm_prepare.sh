#!/usr/bin/env bash
# One-time preparation of the Lucknow road network and OSM extract. Needs Docker, curl and ~1.5 GB
# of free disk. Output (gitignored):
#   data/osm/lucknow.osm.pbf         Lucknow district bbox clip, read by scripts/import_facilities.py
#   data/osrm/lucknow.osrm*          OSRM car-profile MLD graph served by the `osrm` compose service
#   data/osm/SOURCE.txt              where the data came from (URL, MD5, OSM timestamp, bbox)
#
# REGION defaults to Geofabrik's India "central-zone" (~350 MB), which contains all of Lucknow
# district. REGION=asia/india uses the full India extract (~1.7 GB) and gives the same clip.
set -euo pipefail

REGION="${REGION:-asia/india/central-zone}"
# Box around Lucknow district (min_lon,min_lat,max_lon,max_lat, WGS84) with ~0.1 degree margin so
# the district boundary relation (OSM 1959018) is complete; facilities are then filtered to it.
BBOX="${BBOX:-80.45,26.45,81.35,27.25}"
DATA_DIR="${DATA_DIR:-$(pwd)/data}"
OSRM_IMAGE="${OSRM_IMAGE:-ghcr.io/project-osrm/osrm-backend:v6.0.0}"
OSMIUM_IMAGE="${OSMIUM_IMAGE:-debian:bookworm-slim}"
# "simple" fits in a 2 GB Docker VM; ways crossing the bbox edge are cut there, which the margin
# around the district makes harmless. "complete_ways" keeps them whole but needs several GB.
OSMIUM_STRATEGY="${OSMIUM_STRATEGY:-simple}"

mkdir -p "$DATA_DIR/osm" "$DATA_DIR/osrm"
source_name="$(basename "$REGION")-latest.osm.pbf"
source_url="https://download.geofabrik.de/${REGION}-latest.osm.pbf"

if [ ! -f "$DATA_DIR/osm/$source_name" ]; then
  echo "Downloading $source_url"
  curl -fL --retry 3 -o "$DATA_DIR/osm/$source_name.part" "$source_url"
  curl -fsSL -o "$DATA_DIR/osm/$source_name.md5" "$source_url.md5"
  mv "$DATA_DIR/osm/$source_name.part" "$DATA_DIR/osm/$source_name"
fi

echo "Verifying checksum and clipping to $BBOX with osmium"
docker run --rm -v "$DATA_DIR/osm:/data" -w /data "$OSMIUM_IMAGE" sh -euc "
  apt-get update -qq && apt-get install -y -qq osmium-tool >/dev/null
  md5sum -c '$source_name.md5'
  osmium extract --bbox '$BBOX' --strategy '$OSMIUM_STRATEGY' --overwrite \
    -o lucknow.osm.pbf '$source_name'
  osmium fileinfo -e -g data.timestamp.last lucknow.osm.pbf > osm_timestamp.txt
"

cp "$DATA_DIR/osm/lucknow.osm.pbf" "$DATA_DIR/osrm/lucknow.osm.pbf"
echo "Building the OSRM car graph (MLD)"
docker run --rm -v "$DATA_DIR/osrm:/data" "$OSRM_IMAGE" osrm-extract -p /opt/car.lua /data/lucknow.osm.pbf
docker run --rm -v "$DATA_DIR/osrm:/data" "$OSRM_IMAGE" osrm-partition /data/lucknow.osrm
docker run --rm -v "$DATA_DIR/osrm:/data" "$OSRM_IMAGE" osrm-customize /data/lucknow.osrm
rm "$DATA_DIR/osrm/lucknow.osm.pbf"

cat > "$DATA_DIR/osm/SOURCE.txt" <<SOURCE
source: $source_url
md5: $(cut -d' ' -f1 "$DATA_DIR/osm/$source_name.md5")
osm_data_timestamp: $(cat "$DATA_DIR/osm/osm_timestamp.txt")
bbox: $BBOX
osmium_strategy: $OSMIUM_STRATEGY
osrm_image: $OSRM_IMAGE
licence: OpenStreetMap data (c) OpenStreetMap contributors, ODbL 1.0
SOURCE
echo "Done. See $DATA_DIR/osm/SOURCE.txt"
