#!/bin/sh
# Entry point for the `api` compose service: migrate, load the Lucknow data if prepared, serve.
set -eu

alembic -c backend/alembic.ini upgrade head

if [ -f "${OSM_EXTRACT:-}" ]; then
  if [ -n "${AEGISOPS_OSRM_URL:-}" ]; then
    # Plan the seeded exercise on road times: give OSRM up to 60 s to start listening.
    python - <<'PY'
import os, time, httpx
url = os.environ["AEGISOPS_OSRM_URL"].rstrip("/") + "/nearest/v1/driving/80.9448,26.8548"
for _ in range(60):
    try:
        if httpx.get(url, timeout=2).status_code == 200:
            break
    except httpx.HTTPError:
        pass
    time.sleep(1)
else:
    print("OSRM did not answer; the seeded decision will carry the degraded flag")
PY
  fi
  python scripts/import_facilities.py "$OSM_EXTRACT"
  python scripts/seed_lucknow_exercise.py "$OSM_EXTRACT" --record-decision
else
  echo "No OSM extract at '${OSM_EXTRACT:-}'. Run scripts/osrm_prepare.sh for the Lucknow" \
       "exercise; seeding a synthetic decision instead." >&2
  python -m backend.seed
fi

exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
