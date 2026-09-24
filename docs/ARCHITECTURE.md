# AegisOps architecture

This replaces the earlier SRS, SAD, HLD and LLD, which described the system before the solver,
verifier, audit chain, geodata and console were built. Each statement points to the file or
test that shows it. The reasons for the four central decisions are in [adr/](adr/).

## 1. Purpose and boundaries

AegisOps is a research platform. It turns field reports about a flood exercise in Lucknow into
response plans that a human approves or rejects, with every number re-checked and every
decision replayable.

What it must never do:

- dispatch anything;
- connect to real dispatch, real personal data or live operations;
- let a model's number reach an operator unverified.

Every `DecisionResult` carries `requires_human_approval=True`
(`aegisops/application/decision_service.py`). No code path acts on an approval.

## 2. The pipeline

| Step | What happens | Where | Deterministic? |
| --- | --- | --- | --- |
| Read | A free-text report (English, Hindi, Hinglish) becomes a typed candidate. Every field quotes the report, and a field whose quote is not in the report is dropped. Severity comes from rules R1–R9. The place comes from an OSM gazetteer. An operator confirms the facts in triage. | `aegisops/intake/` (`reader.py`, `grounding.py`, `severity.py`, `gazetteer.py`, `triage.py`); `aegisops/api/intake_api.py` | Model call, then deterministic grounding |
| Plan | CP-SAT assigns units over a travel-time matrix, honouring typed constraints (reserve, exclude, priority). Infeasible constraints are named. | `aegisops/planning/solver.py`, `constraints.py`, `objective.py` | Yes |
| Travel times | OSRM table service (car profile), cached. On failure it falls back to straight-line times, marked `degraded`. | `aegisops/planning/osrm.py`, `providers.py` | Yes, given OSRM |
| Verify | 19 pure checks on any plan: units exist, are available and are used once; capability and quantity; ETAs recomputed; critical coverage; objective vs the CP-SAT optimum; constraints; citations; SITREP numbers; the approval flag; instruction-like text. | `aegisops/verification/verifier.py` | Yes (see ADR 002) |
| Decide | A human approves or rejects with a reason code. Approval needs the approver role; the proposer cannot approve; a blocked plan cannot be approved. | `aegisops/api/app.py` (disposition), `aegisops/application/dispositions.py`, `src/features/plan/ActionBar.tsx` | Human |
| Communicate | The model drafts SITREP prose and a CAP 1.2 alert from verified facts, and every number is re-checked. CAP status is always `Draft`; nothing is published. | `aegisops/communication/reporter.py`, `sitrep.py` | Model call, then deterministic check |
| Record | The full decision record, plus hash-chained events for every step. Any plan can be re-verified from the stored record alone. | `aegisops/infrastructure/decision_store.py`, `aegisops/audit/event_log.py`, `aegisops/application/replay.py` | Yes (see ADR 003) |

**Where the rule is still broken.** The LLM allocation engine
(`aegisops/infrastructure/llm_decision_engine.py`, `engine=llm_rag`) still proposes
assignments. It is kept as the experiment arm for `evals/llm_vs_solver.py`, and it is safe only
because every proposal goes through the verifier (ADR 001).

## 3. Layers and packages

```text
src/ (React console) ──HTTP/SSE──> aegisops/api (FastAPI)
                                      │
      aegisops/application  ── DecisionService, replay, dispositions, scenario generation
      aegisops/domain       ── Pydantic contracts, policy
      aegisops/planning     ── solver, objective, constraints, OSRM, routes
      aegisops/verification ── verifier, number checks, injection patterns
      aegisops/intake       ── reader, grounding, severity, gazetteer, constraints, triage
      aegisops/communication── SITREP renderer, reporter (drafts)
      aegisops/llm          ── one OpenAI-compatible client, cassettes
      aegisops/audit        ── hash-chained event log
      aegisops/geodata      ── OSM facilities, units, the Lucknow exercise, display labels
      aegisops/ingestion    ── SACHET CAP, USGS, GDACS feed worker
      aegisops/telemetry    ── OpenTelemetry GenAI spans
      aegisops/study        ── user-study tasks and scoring
backend/  ── ASGI entry, SQLAlchemy models, Alembic migrations, seeds (exercise, demo, reset)
```

The domain, planning and verification packages import no I/O. The verifier is called with data
and returns data. API and infrastructure depend inward, never the reverse.

## 4. Data

Relational store: PostgreSQL 16 + PostGIS in compose, where locations are
`geography(Point,4326)` via `backend/db/types.py:GeoPoint`; SQLite in tests and in the demo.
Every schema change is an Alembic migration, and `alembic check` is clean (CI).

| Table | Holds |
| --- | --- |
| `decisions` | The full record: scenario and its SHA-256, plan, verification report, SITREP, constraints and the note behind each, travel matrix, objectives, proposer, trace context |
| `approvals` | One disposition per decision: approver, action, reason code |
| `events` | The append-only hash chain (`prev_hash`, `hash`) over everything above and intake |
| `intake_reports` | Report text, grounded candidate, model/prompt/cost, review reasons, confirmed fields, merges |
| `exercises` | Saved scenarios (the Lucknow exercise) |
| `facilities`, `units` | OSM hospitals and fire and police stations; units stationed at them |
| `alerts`, `feed_polls` | Ingested hazard alerts (raw payload kept) and every feed poll, including failures |
| `study_sessions`, `study_tasks` | User-study sessions: interface, task, right answer, start time |
| `users`, `roles`, `incidents`, `evidence`, `audit_log` | From the first schema; `users` gets a row per approver, the rest are unused by current routes |

## 5. Interfaces

- **API** (`aegisops/api/`, `/docs` when debug):
  - decisions: create, get, list, baseline, routes, re-verify, drafts, disposition
  - intake: read, store, confirm, merge, dismiss, severity preview
  - constraints/translate
  - status, events, labels, places, reports, reason codes, alerts, exercises
  - `stream` (SSE with single-use tickets), `audit/verify`, `study/*`
  - `dev/token` in development only; `demo/token` in demo only
- **Console** (`src/`): operations board, plan review, triage, audit, evals and study, with
  live updates over SSE.
- **Model** (`aegisops/llm/client.py`): any OpenAI-compatible endpoint (NVIDIA NIM by default).
  Output is schema-constrained; tests record and replay cassettes.
- **External data**: OSRM, OpenFreeMap tiles, SACHET, USGS and GDACS. Sources and licences
  are in the README.

## 6. Security and safety controls

- Authentication is by JWT bearer token (HS256 with a real secret, or RS256 via JWKS). The
  server refuses the published development key outside development and tests
  (`aegisops/api/auth.py`). No OIDC login flow is built.
- Roles run viewer < operator < approver < admin (`aegisops/application/roles.py`).
  Separation of duties is covered in ADR 004.
- Input is validated by Pydantic with unknown fields rejected. A 422 names the fields and never
  echoes the submitted values.
- Responses carry request IDs and security headers; CORS allows only configured origins;
  requests are rate-limited.
- Report text is data, never instructions. Instruction-like text is flagged (the verifier and
  triage) and never obeyed. Model output is only accepted through a schema and then re-checked.
- The public demo is a sandbox: two fixed identities with roles set by the server, no model,
  and an hourly reset (`aegisops/api/demo.py`, `backend/demo_reset.py`).

## 7. Deployment

- `docker compose up --build` runs PostGIS, OSRM (Lucknow graph), Phoenix (traces), the API,
  the feed worker and the console.
- The demo configuration is in `railway.json`, `deploy/osrm/` and `vercel.json`, with a guide in
  [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md). The demo is configured but not deployed.

## 8. Evidence of quality

| What | Where |
| --- | --- |
| Backend tests (pytest), including property tests and fault injection | `tests/` |
| Verifier fault injection: 13 classes × 50 scenarios | `reports/fault_injection.md` |
| Console unit tests (Vitest), including WCAG contrast of every token pair | `src/**/*.test.ts(x)` |
| End-to-end flow, layout at 1440×900, and axe on every screen in both themes (Playwright) | `e2e/` |
| CI: lint, types, tests, PostGIS, frontend, e2e, container, smoke eval | `.github/workflows/ci.yml` |
| LLM evaluations: harness built, not yet run against a live model | `evals/`, `reports/README.md` |

## 9. Not built

- OIDC sign-in.
- Traffic-aware or flood-aware routing (OSRM gives free-flow car times).
- Turning ingested alerts into incidents.
- Any live-model result.
- A deployed public demo.
- Multi-agent anything: `backend/agents/roles.py` holds data-only role stubs.
