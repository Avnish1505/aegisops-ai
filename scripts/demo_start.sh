#!/bin/sh
# Public demo API (Railway): migrate, import the Lucknow facilities (names for units), reset the
# sandbox, then serve one process (stream tickets and the reset schedule live in memory).
# Needs AEGISOPS_ENVIRONMENT=demo and a real AEGISOPS_SECRET_KEY; see docs/DEPLOYMENT_GUIDE.md.
set -eu
alembic -c backend/alembic.ini upgrade head
python scripts/import_facilities.py deploy/osm/lucknow.osm.pbf
python -m backend.demo_reset
exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
