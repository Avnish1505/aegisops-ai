# Incident Response Runbook

## Scope

This runbook covers operational incidents affecting the AegisOps AI **platform itself**
(API availability, data integrity, security of the running service) — for example, the
API returning errors, a failed deployment, a database outage, or abuse of an endpoint.

It is distinct from the domain content under [`knowledge/`](../knowledge/), which governs
how the *simulated* decision engine reasons about *fictional* crisis scenarios
(see `knowledge/escalation-protocol.md`, `knowledge/incident-triage.md`,
`knowledge/safety-gates.md`). This document is about keeping the service that hosts that
simulation online and trustworthy.

As elsewhere in this project, no step here authorises an unattended automated action —
every recovery or rollback step is executed by an authorised operator, consistent with the
human-approval principle in `knowledge/human-approval.md`.

## Detection

Signals that indicate an incident, in order of how they are typically noticed:

- **Health checks failing.** `GET /health/live` (process liveness) or `GET /health/ready`
  (dependency readiness, includes `environment`) returns non-200, times out, or the
  container's Docker `HEALTHCHECK` (see `Dockerfile`) reports unhealthy. Railway and any
  container orchestrator will restart-loop the service on repeated failures.
- **Elevated error rate in logs.** The app logs structured JSON (`aegisops/core/logging.py`)
  with a `request_id` on every request. An `unhandled_error request_id=...` log line
  (`aegisops/api/app.py`) paired with a 500 response indicates an unhandled exception —
  scenario/decision payloads are never logged, so these lines are safe to share when
  escalating.
- **Rate-limit exhaustion (429s).** A spike in `429` responses from the `slowapi` limiter
  (`RATE_LIMIT` setting, default `100/minute`, enforced on `/health/*`, `/metrics`,
  `/api/v1/scenarios`, `/api/v1/decisions`) can indicate either a misbehaving client, a
  misconfigured integration, or a denial-of-service attempt.
- **`/metrics` scrape failures.** The Prometheus endpoint (`GET /metrics`) going dark or
  returning malformed output means monitoring itself may be degraded — treat as high
  priority since it blinds further detection.
- **Deployment platform alerts.** Railway build/deploy failures, a Vercel build failure for
  the static frontend, or a Docker image failing to start (see `docs/../ENVIRONMENT.md` for
  the deployment surfaces introduced in Bundle 19).
- **Security signals.** Repeated `401`/`403` responses from `require_operator`-protected
  routes, or CORS rejection spikes, may indicate credential probing.

## Escalation

Use the same severity framing as `knowledge/incident-triage.md`, applied to platform health
instead of simulated scenarios:

| Severity | Definition | Example | Action |
| --- | --- | --- | --- |
| Critical | Service fully unavailable, data loss/corruption risk, or a confirmed security breach | `/health/live` failing across all instances; database unreachable; secret leak | Escalate immediately to the on-call operator; do not wait for confirmation before paging |
| High | Core functionality degraded but partially available | `/api/v1/decisions` erroring for one engine; sustained 429s from a single source | Escalate within the current shift |
| Medium | Non-critical functionality affected | `/metrics` slow but responsive; intermittent 5xx | Log and review at next operational check-in |
| Low | Cosmetic or transient issue with no user impact | Single retried request; brief log noise | Record for trend analysis only |

Escalation requires: the affected endpoint(s), the `request_id`(s) from the logs, the
observed signal (status code, log line, or alert), and the current deployment target
(Docker/Railway/Vercel). As with `knowledge/escalation-protocol.md`, escalating does not
itself authorise a fix — recovery and rollback actions below still require an authorised
operator to execute them.

## Recovery

Work through these in order; stop once the health checks in **Verification** pass.

1. **Confirm scope.** Hit `/health/live` and `/health/ready` directly against the affected
   deployment to distinguish a total outage from a degraded dependency.
2. **Check configuration and secrets.** Confirm `SECRET_KEY`, `DATABASE_URL`,
   `AEGISOPS_CORS_ORIGINS`, and `RATE_LIMIT` are set as expected for the environment (see
   `ENVIRONMENT.md`); a bad or missing value is a common cause of boot failure.
3. **Restart the service.**
   - Docker Compose: `docker-compose restart web`
   - Docker (standalone): `docker restart <container>`
   - Railway: trigger a redeploy of the current build from the Railway dashboard/CLI.
4. **Database connectivity.** If `/health/ready` succeeds but requests touching the database
   fail, verify the target in `DATABASE_URL` is reachable. For the default SQLite mode,
   confirm the `/app/data` volume (declared in `Dockerfile`/`docker-compose.yml`) is mounted
   and writable by the `appuser` account.
5. **Rate-limit exhaustion.** If the cause is legitimate load rather than abuse, raise
   `RATE_LIMIT` for the affected environment and redeploy; if it is abuse, block the source
   at the platform/network layer before relaxing the limit.
6. **Escalate to rollback** if recovery does not restore service within the incident's
   severity-appropriate window (see Escalation table).

## Rollback

Roll back when a recent deploy is the suspected cause, or recovery steps fail to restore
service.

1. **Application (Docker/Railway).** Redeploy the last known-good image/build:
   - Railway: use "Redeploy" on the last successful deployment in the Railway dashboard, or
     `railway up` from the last good commit.
   - Docker: re-tag and run the previous image (`docker run ... aegisops-ai:<previous-tag>`).
2. **Frontend (Vercel).** Use Vercel's deployment history to promote the last known-good
   deployment (routes are static per `vercel.json`, so this is a direct swap with no server
   state to reconcile).
3. **Database migrations.** If a schema migration is implicated, downgrade one revision with
   Alembic from `backend/`: `alembic -c alembic.ini downgrade -1`. Confirm the application
   version being rolled back to is compatible with the downgraded schema before restarting
   it.
4. **Configuration.** Revert any environment variable change made during recovery (step 2
   above) that did not resolve the incident, so the rollback isn't masked by an unrelated
   config change.

## Verification

An incident is resolved only once all of the following hold:

1. `GET /health/live` returns `200 {"status": "ok"}`.
2. `GET /health/ready` returns `200` with the expected `environment` value.
3. `GET /metrics` returns `200` with a non-empty Prometheus body.
4. A representative request (`GET /api/v1/scenarios`) succeeds end-to-end and the response
   carries an `X-Request-ID` header.
5. Logs show no new `unhandled_error` entries for the affected `request_id` range.
6. Error and 429 rates have returned to baseline.
7. For rollbacks touching tests, the relevant suite passes locally against the restored
   version: `pytest tests/test_observability.py tests/test_api.py tests/test_security.py`.

Record the incident timeline, root cause, and the recovery or rollback action taken once
verification passes, so it can inform future detection and escalation thresholds.
