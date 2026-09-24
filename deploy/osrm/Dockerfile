# OSRM for the public demo: the Lucknow road graph is built into the image at build time.
FROM ghcr.io/project-osrm/osrm-backend:v6.0.0
COPY deploy/osm/lucknow.osm.pbf /data/lucknow.osm.pbf
RUN osrm-extract -p /opt/car.lua /data/lucknow.osm.pbf \
 && osrm-partition /data/lucknow.osrm \
 && osrm-customize /data/lucknow.osrm \
 && rm /data/lucknow.osm.pbf
# Railway sets PORT; locally it defaults to 5000.
CMD ["sh", "-c", "exec osrm-routed --algorithm mld --max-table-size 1000 --port ${PORT:-5000} /data/lucknow.osrm"]
