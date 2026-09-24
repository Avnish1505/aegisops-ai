#!/bin/sh
# API for the Playwright tests: a fresh SQLite database with the Lucknow exercise (from its
# committed snapshot, straight-line travel times) and the demo triage reports. No model, no OSRM.
set -eu
DB="${E2E_DB:-${TMPDIR:-/tmp}/aegisops-e2e.db}"
rm -f "$DB"
export AEGISOPS_DATABASE_URL="sqlite:///$DB"
export AEGISOPS_ENVIRONMENT=development
export PYTHONPATH="${PYTHONPATH:-.}"
export AEGISOPS_CORS_ORIGINS="http://localhost:4173"
unset AEGISOPS_OSRM_URL AEGISOPS_LLM_API_KEY NVIDIA_API_KEY
alembic -c backend/alembic.ini upgrade head
python -m backend.snapshot_seed
python scripts/seed_demo_intake.py
exec uvicorn backend.main:app --port 8010
