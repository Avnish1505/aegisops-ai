# Deployment Guide

This guide walks through taking AegisOps AI from a checked-out repository to a running
deployment, and what to do when that deployment misbehaves. It builds on the deployment
configuration added in Bundle 19 (`Dockerfile`, `docker-compose.yml`, `railway.json`,
`vercel.json`, `ENVIRONMENT.md`) and the operational practices in
[`INCIDENT_RESPONSE_RUNBOOK.md`](INCIDENT_RESPONSE_RUNBOOK.md). It does not replace either —
see [`ENVIRONMENT.md`](../ENVIRONMENT.md) for the full environment variable reference and the
runbook for incident-scale detection/escalation.

For local development (not deployment), see [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md).

## Setup

Before deploying, verify the build works locally:

```bash
git clone <repository-url>
cd aegisops-ai
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
npm install && npm run build   # produces the static frontend in dist/
```

Install whichever platform CLI you're targeting:

- Docker: [Docker Desktop](https://docs.docker.com/get-docker/) or a compatible engine.
- Railway: `npm i -g @railway/cli`, then `railway login`.
- Vercel: `npm i -g vercel`, then `vercel login`.

Confirm the backend runs locally before deploying: `uvicorn backend.main:app --port 8000`
and `curl http://localhost:8000/health/live`.

## Environment

All runtime configuration is via environment variables, defined in
`aegisops/core/config.py` and documented in full in [`ENVIRONMENT.md`](../ENVIRONMENT.md)
(variable names, defaults, and an example `.env`). At minimum, set for any non-local
deployment:

- `SECRET_KEY` — must be overridden from its development default.
- `DATABASE_URL` — SQLite is the default; use a managed Postgres URL for production.
- `AEGISOPS_ENVIRONMENT=production` and `AEGISOPS_DEBUG=false` — disables `/docs` and
  verbose debug logging.
- `AEGISOPS_CORS_ORIGINS` — set to the exact production frontend origin(s); never wildcard.

Never commit populated `.env` files; `.env.example` is the template and `.gitignore`
already excludes `.env`.

## Deployment

### Docker / Docker Compose

```bash
docker build -t aegisops-ai .
docker run -p 8000:8000 \
  -e AEGISOPS_ENVIRONMENT=production \
  -e AEGISOPS_DEBUG=false \
  -e SECRET_KEY=<your-secret> \
  aegisops-ai
```

For local multi-container testing, `docker-compose up` uses `docker-compose.yml`, which
mounts the working tree and a persistent `/app/data` volume for the SQLite database.

### Railway (backend/API)

`railway.json` points Railway at the repository `Dockerfile`. From a logged-in CLI session:

```bash
railway init
railway up
```

Set the environment variables from the section above in the Railway project dashboard (or
`railway variables set KEY=VALUE`) before the first deploy that serves real traffic.

### Vercel (frontend)

`vercel.json` builds the frontend as a static site (`@vercel/static-build`, `dist/`) with a
catch-all SPA route. From a logged-in CLI session, `vercel` deploys the current directory;
`vercel --prod` promotes it to the production alias.

## Monitoring

Once deployed, the service exposes three signals worth watching continuously:

- **Liveness/readiness**: `GET /health/live` and `GET /health/ready` — point your platform's
  health-check or uptime monitor at these. `Dockerfile` already wires `/health/live` into the
  container `HEALTHCHECK`.
- **Metrics**: `GET /metrics` returns Prometheus-format output (`prometheus_client`). Point a
  Prometheus scrape config or compatible collector at it.
- **Structured logs**: every request is logged as JSON (`aegisops/core/logging.py`) with a
  `request_id` that also comes back on the response as the `X-Request-ID` header, so a
  user-reported error can be traced to a specific log line. Scenario/decision payload content
  is intentionally never logged.

Baseline alerting worth configuring on top of these: health-check failures over N
consecutive checks, 5xx rate above baseline, and sustained 429 (rate-limit) responses.

## Rollback

If a deployment introduces a regression, roll back rather than forward-fixing under
pressure:

- **Railway**: redeploy the last known-good deployment from the Railway dashboard, or
  `railway up` from the last good commit.
- **Docker**: run the previous image tag.
- **Vercel**: promote the previous deployment from the Vercel dashboard's deployment
  history — this is a direct swap since the frontend is static.
- **Database schema**: if a migration is implicated, `alembic -c backend/alembic.ini
  downgrade -1` before rolling back the application code that depended on it.

For an in-progress incident, follow the full Rollback and Verification steps in
[`INCIDENT_RESPONSE_RUNBOOK.md`](INCIDENT_RESPONSE_RUNBOOK.md#rollback) rather than
improvising — it defines the severity levels and confirms when a rollback is actually
warranted.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Container marked unhealthy immediately | `HEALTHCHECK` can't reach `/health/live`, or the app failed to boot | Check `docker logs` for a startup exception before assuming the healthcheck itself is broken |
| Environment variable seems to have no effect | `aegisops/core/config.py` uses case-sensitive settings matching the exact field name (e.g. `debug`, `rate_limit`); some documented `AEGISOPS_`-prefixed and uppercase names are not currently read by the application | Verify the effective value via `GET /health/ready` (`environment` field) or by inspecting `Settings()` directly; this is a known documentation/code mismatch, not a deployment error |
| CORS errors in the browser | `AEGISOPS_CORS_ORIGINS` does not include the calling origin, or was set on a build where it isn't actually read (see above) | Confirm the origin is in the configured list and matches exactly, including scheme and port |
| `/docs` returns 404 in production | Expected — `docs_url` is disabled unless `AEGISOPS_DEBUG` is effectively true | Do not enable debug mode in production to "fix" this |
| Database errors after deploy | `DATABASE_URL` unreachable, or the `/app/data` volume isn't mounted/writable for SQLite | Check volume mounts and, for managed databases, network/credentials |
| Vercel build fails | `npm run build` fails locally too | Run `npm run build` locally first; fix the underlying `tsc`/`vite` error before redeploying |
| Railway deploy fails | `Dockerfile` build step fails | Reproduce with `docker build -t aegisops-ai .` locally to see the same error without waiting on Railway |
| Sustained 429 responses | Legitimate traffic exceeding `RATE_LIMIT`, or an abusive client | Distinguish the two before raising the limit; block abusive sources at the platform layer |

If a symptom escalates beyond a quick fix, switch to
[`INCIDENT_RESPONSE_RUNBOOK.md`](INCIDENT_RESPONSE_RUNBOOK.md) for detection, escalation, and
verification steps.
