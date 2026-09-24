# AegisOps

AegisOps turns messy incident reports into solver-backed response plans that a human approves,
with every number re-checked and every decision replayable. Research platform, not an emergency
system.

That sentence describes where the project is going. The **Status** table below says what exists
today, and every row points to the file or test that backs it.

## Safety position

This service never dispatches resources. Every recommendation has `requires_human_approval: true`,
and a `blocked` recommendation cannot be approved: the API returns 409. It plans synthetic
scenarios and a fictional exercise set on real Lucknow places; it has no connection to any
emergency service. Do not connect it to emergency operations or use it with real personal or
operational data.

## Quick start

```bash
./scripts/osrm_prepare.sh     # once: ~350 MB Geofabrik download, Lucknow clip, OSRM graph (~2 min)
docker compose up --build
```

`scripts/osrm_prepare.sh` needs Docker and about 1.5 GB of free disk; it writes `data/`
(gitignored) and records the source, checksum and OSM timestamp in `data/osm/SOURCE.txt`. Compose
then runs PostgreSQL + PostGIS, OSRM (car profile), the API, the feed worker and the console
(`docker-compose.yml`). On start the API migrates the database, imports Lucknow facilities, seeds
the exercise and plans it once on OSRM road times (`scripts/compose_api_start.sh`). Open
http://localhost:5173, choose **Lucknow monsoon flood exercise**, then **Get recommendation**.
Without the prepared data the API seeds a synthetic decision instead.

Without Docker (Python 3.11–3.13, Node 22):

```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements-dev.txt
alembic -c backend/alembic.ini upgrade head
AEGISOPS_ENVIRONMENT=development AEGISOPS_DEBUG=true uvicorn backend.main:app --reload --port 8000
npm ci && npm run dev          # console on http://localhost:5173
```

Settings are read from `AEGISOPS_`-prefixed environment variables (`aegisops/core/config.py`,
[ENVIRONMENT.md](ENVIRONMENT.md)).

## Status

| Area | State | Evidence |
| --- | --- | --- |
| Synthetic scenarios | ✅ The same seed always gives the same scenario | `aegisops/application/scenario_service.py`; `tests/test_api.py::test_scenario_endpoint_is_reproducible_and_sets_request_id` |
| Planning | ✅ CP-SAT assignment minimising severity-weighted travel plus a penalty per unmet unit; typed reserve / exclude / priority constraints; infeasible constraints are named. The greedy engine is kept as a baseline. ⚠️ Synthetic scenarios place random WGS84 points in urban Lucknow | `aegisops/planning/solver.py`; `tests/test_solver.py` |
| Fault injection | ✅ 13 fault classes × 50 seeded scenarios: every injected fault caught by its check (650/650); 0 of 50 clean solver plans falsely blocked. [Report](reports/fault_injection.md) | `tests/fault_injection/`; `scripts/fault_report.py` |
| Safety gates | ✅ An unmet critical requirement blocks the plan | `tests/test_decision_engine.py::test_engine_blocks_critical_unmet_capability` |
| Road travel times | ✅ With `AEGISOPS_OSRM_URL` set, ETAs come from an OSRM table request (car profile), cached by input hash; the verifier re-checks every ETA against that matrix. If OSRM is down, straight-line estimates are used and the plan carries a visible degraded flag (banner plus a high-severity check). ⚠️ OSRM car speeds are free-flow: no traffic, closures or flooding | `aegisops/planning/osrm.py`; `tests/test_osrm.py` |
| Verification | ✅ Every engine's plan goes through 19 deterministic checks (units, availability, duplicates, capability, quantities, travel times recomputed within max(1 min, 5%) and whether they are degraded fallbacks, critical coverage, objective vs the CP-SAT optimum, constraints, citations and quotes, SITREP numbers, approval flag, instruction-like report text). Any critical failure blocks; the API returns the full report | `aegisops/verification/verifier.py`; `tests/test_verifier.py`; `tests/test_llm_decision_engine.py` |
| LLM client | ✅ One OpenAI-compatible client configured by env (default NVIDIA NIM, `nvidia/llama-3.1-nemotron-70b-instruct`). Output is schema-constrained (NIM `guided_json`, otherwise `response_format` JSON schema) and validated with Pydantic; each call logs model, prompt version, tokens, latency and estimated cost. Record/replay cassettes store no headers. ⚠️ Not yet run against the live endpoint, so `guided_json` support on this model is unconfirmed | `aegisops/llm/client.py`; `tests/test_llm_client.py` |
| LLM allocation engine (`llm_rag`) | ⚠️ Kept as an experiment arm; it breaks the target rule (the LLM proposes assignments) and is only safe because the verifier blocks bad plans. **Not evaluated against a live model**: every test uses a mocked response. Without a key it returns `blocked` | `aegisops/infrastructure/llm_decision_engine.py`; `tests/test_llm_decision_engine.py` |
| Read (free-text intake) | ✅ `POST /api/v1/intake/read`: English, Hindi or Hinglish report → incident candidate. Every field carries a quote; a field whose quote is not in the report, or whose number the quote does not state, is dropped and counted. Severity comes from deterministic rules R1–R9, not the model. Places are geocoded with a 1,819-entry Lucknow gazetteer built from OSM. ⚠️ Tested with mocked and oracle models only; no live accuracy yet | `aegisops/intake/`; `tests/test_reader.py` |
| Constraint translator | ✅ `POST /api/v1/constraints/translate`: an operator note becomes one typed reserve / exclude / priority constraint, shown for confirmation; the solver only uses constraints the operator sends back. ⚠️ No live accuracy yet | `aegisops/intake/constraints.py`; `tests/test_constraint_translator.py`; `src/components/ConstraintPanel.tsx` |
| Communicate | ✅ `POST /api/v1/decisions/{id}/drafts`: SITREP (ICS-201-style sections) and CAP 1.2 alert drafts. The model writes prose from verified facts; every number is re-checked and a draft that fails says so. CAP status is always `Draft`, scope `Private`; nothing is published. ⚠️ No live run yet | `aegisops/communication/reporter.py`; `tests/test_reporter.py` |
| Tracing | ✅ OpenTelemetry spans with GenAI conventions (`chat` for model calls, `execute_tool` for travel matrix, solve, propose, verify). One decision is one trace across requests: read returns a W3C `traceparent`, the plan stores it, and decide/drafts join it. Compose exports to self-hosted Arize Phoenix (:6006) | `aegisops/telemetry/__init__.py`; `tests/test_telemetry.py` |
| Retrieval | ⚠️ **Keyword hashing, not semantic search.** Tokens are hashed into 256 buckets and ranked by inner product | `aegisops/infrastructure/knowledge_retrieval.py`; `tests/test_knowledge_retrieval.py` |
| Real facilities | ✅ Hospitals, fire stations and police stations inside Lucknow district (OSM boundary relation 1959018) are imported from a local OSM extract, never Overpass: 270 hospitals, 27 police stations, 3 fire stations in the 2026-09-22 extract. ⚠️ OSM maps only 3 fire stations in the district, fewer than exist. Units are stationed at them by documented exercise rules; OSM has no unit counts | `aegisops/geodata/`; `scripts/import_facilities.py`; `tests/test_geodata.py` |
| Lucknow exercise | ✅ 20 fictional monsoon-flood incidents across Charbagh, Hazratganj, Aminabad, Chowk, Aliganj, Gomti Nagar, Indira Nagar, Alambagh and Kaiserbagh, placed at those localities' OSM place nodes, against 45 units (ambulances, boats, rescue teams, fire units) stationed at real facilities. Loadable from the console | `aegisops/geodata/exercise.py`; `scripts/seed_lucknow_exercise.py`; `tests/test_exercise.py` |
| Hazard feeds | ✅ A worker (APScheduler; reasons in the module docstring) polls NDMA SACHET's CAP 1.2 feed, USGS `all_day` GeoJSON and the GDACS event list, stores source, `fetched_at` and the raw payload, and dedupes on (source, identifier). CAP is parsed per the 1.2 spec with hostile-XML protection. Tests use recorded fixtures only. A live run on 2026-09-23 stored 99 SACHET, 233 USGS and 95 GDACS alerts with 0 CAP documents rejected. ⚠️ Alerts are stored and listed (`GET /api/v1/alerts`), not yet turned into incidents | `aegisops/ingestion/`; `tests/test_ingestion.py` |
| Human decision | ✅ Approve/reject needs a reason code that fits the action (`other` needs text), stored on the approval and in the hashed event. Blocked decisions return 409 | `tests/test_persistence_integration.py::test_blocked_decision_cannot_be_approved_or_create_disposition` |
| Proposer ≠ approver | ✅ Each decision records the proposer's token subject; approving needs the `approver` role and the same subject gets 409 "proposer cannot approve" | `tests/test_auth.py::test_proposer_cannot_approve_their_own_decision` |
| Decision record | ✅ Stores the input scenario and its SHA-256, the plan, verification report, SITREP, constraints, travel matrix, and prompt/model versions. A stored record replays and re-verifies to the same result | `tests/test_persistence_integration.py::test_stored_decision_replays_and_reverifies_to_the_same_result` |
| Audit log integrity | ✅ Decisions, verifications and dispositions append to a hash-chained `events` table; each event also hashes the decision/approval row it created. `GET /api/v1/audit/verify` reports the first broken link, and editing any event column, deleting an event, or editing a decision or approval row is detected. ⚠️ Deleting the newest event is only detectable against an externally kept `head_hash` | `aegisops/audit/event_log.py`; `tests/test_event_chain.py` |
| Auth | ✅ JWT bearer tokens with `sub` and `role`: HS256 with `AEGISOPS_SECRET_KEY`, or RS256 against an OIDC JWKS. The server refuses to start outside development with the published dev key. ⚠️ The console has only the development sign-in (`/api/v1/dev/token`, `AEGISOPS_ENVIRONMENT=development`) and the demo's two fixed identities (`/api/v1/demo/token`, roles set by the server); no OIDC login flow is built | `aegisops/api/auth.py`; `aegisops/api/demo.py`; `tests/test_auth.py`; `tests/test_demo.py` |
| Operations console | ✅ React console on ISA-101 lines: grey canvas, colour only for abnormal (red critical, amber high, magenta blocked), severity always shape + colour + word, WCAG AA contrast checked in a test. Operations board (priority queue, MapLibre + deck.gl map with OSRM routes and CAP areas, inspector, live audit timeline over SSE), plan review (verified ETAs, verifier checklist, baseline diff, SITREP mismatches marked, sticky Approve/Reject of equal weight with reason codes and a confirm step), intake triage (quote highlights, rule-based review reasons, duplicates, confirm into the exercise), audit (hash chain, re-verify stored inputs), evals (committed reports only). Keyboard: J/K, Enter, A, R, ⌘K, ?. ✅ Playwright: triage → plan → review → approve by a second user, Approve inside 1440×900, axe with no WCAG A/AA violations on every screen in both themes, no console errors | `src/`; `e2e/`; `src/design/tokens.test.ts` |
| Public demo | ⚠️ Configured, not deployed yet: resettable sandbox (hourly reset), fixed operator/approver identities, no model, OSRM built from the committed Lucknow extract | `aegisops/api/demo.py`; `backend/demo_reset.py`; `deploy/`; `docs/DEMO.md` |
| Multi-agent | ❌ None. `backend/agents/roles.py` holds data-only role descriptions | `backend/agents/roles.py` |
| Database | ✅ Compose runs PostgreSQL 16 + PostGIS; locations are `geography(Point,4326)`. Every migration runs up, down and up again on PostGIS in CI, with a geography round trip and an API + audit-chain run. The unit tests use SQLite | `tests/test_postgres.py`; `docker-compose.yml` |
| Evaluation | ✅ Golden-scenario regression suite for the rule-based engine. ✅ LLM eval harness: 300 labelled reports (200 synthetic Lucknow reports in English/Hindi/Hinglish, 100 HumAID tweets by ID), 50 operator notes, 50 end-to-end scenarios and 100 OSRM scenarios for LLM vs CP-SAT, with bootstrap CIs. The scoring is checked against an oracle model. ❌ **Not run against a live model yet**: see Results | `evals/`; `tests/test_evals.py`; `tests/test_llm_vs_solver.py` |
| Delivery | ✅ CI runs Python lint/types/tests (3.11), a PostGIS job, frontend lint/typecheck/Vitest/build, the Playwright + axe job, and a container smoke test that requires 200 from `/health/ready` and a seeded `POST /api/v1/decisions`. A keyless smoke eval replays recorded LLM cassettes (⚠️ none recorded yet, so it only warns); the full eval is a manual workflow using the `NVIDIA_API_KEY` secret | `.github/workflows/ci.yml`; `.github/workflows/eval.yml` |
| Logging | ✅ JSON logs carry an ISO-8601 UTC `timestamp`, `level`, and `request_id` | `tests/test_observability.py::test_json_log_record_has_real_timestamp_and_level` |

## Results

**No live-model results yet.** The eval harness (`evals/run.py`) and the LLM-vs-solver experiment
(`evals/llm_vs_solver.py`) are built, and their scoring is tested against oracle models
(`tests/test_evals.py`, `tests/test_llm_vs_solver.py`). Neither has been run against the hosted
model, because no API key was available. Until they have, this README claims no accuracy,
feasibility, latency or cost numbers for any LLM step. The earlier "LLM blocked 30/30" report is
superseded: it was produced without a key ([reports/README.md](reports/README.md)).

## Architecture

```text
console (src/: React, TanStack Router/Query, MapLibre + deck.gl on OpenFreeMap tiles, SSE) -> FastAPI (aegisops/api)
   read: report -> LLM (aegisops/intake/reader.py) -> grounded candidate, rule-based severity
   note -> LLM (aegisops/intake/constraints.py) -> proposed constraint -> operator confirms
   DecisionService: engine proposal (solver | rule_based | llm_rag) -> CP-SAT reference
                    -> SITREP -> verify
   drafts: verified plan -> LLM prose (aegisops/communication/reporter.py) -> numbers re-checked
   traces: OpenTelemetry -> Arize Phoenix (compose)
   travel times: OSRM table service (aegisops/planning/osrm.py), straight-line fallback
   storage: PostgreSQL/PostGIS (SQLite in tests): decisions, approvals, events (hash chain),
            facilities, units, exercises, alerts
feed worker (aegisops/ingestion/worker.py): SACHET CAP, USGS, GDACS -> alerts
```

The target pipeline is Read → Plan → Verify → Decide → Communicate → Record. In it, the LLM only
parses input and drafts messages, and deterministic code checks every number before an operator
sees it. The Status table lists which of those steps exist today.

## Repository layout

- `aegisops/domain`: validated entities and deterministic policy/verification functions.
- `aegisops/application`: scenario generation, ports, and the shared `UserRole` enum.
- `aegisops/infrastructure`: rule-based and NIM engines, retrieval, decision persistence.
- `aegisops/api`: FastAPI transport, dev-only role checks, error handling, headers.
- `backend`: ASGI entry point, SQLAlchemy models, Alembic migrations, demo seed.
- `sim`: golden scenarios, evaluation harness, engine comparison.
- `src`: React + Vite operations console.
- `tests`: pytest suite.

## Implementation Integrity Analyzer

A separate static-analysis research tool lives in `aegisops/integrity_analyzer`. Design,
limitations, and its benchmark against a naive grep baseline:
[docs/INTEGRITY_ANALYZER.md](docs/INTEGRITY_ANALYZER.md).

## Data sources and licences

| Source | Used for | Licence / terms |
| --- | --- | --- |
| [OpenStreetMap](https://www.openstreetmap.org) via [Geofabrik](https://download.geofabrik.de/asia/india.html) India extracts | Road network (OSRM), hospitals, fire and police stations, locality places, district boundary (relation 1959018) | Map data © OpenStreetMap contributors, [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Derived data in `data/` stays under the ODbL. |
| [OpenFreeMap](https://openfreemap.org) vector tiles (OpenMapTiles schema) | Console basemap (shown in greyscale) | Map data © OpenStreetMap contributors (ODbL); © OpenMapTiles; attribution shown on the map |
| [OSRM](https://project-osrm.org) `osrm-backend` v6.0.0 | Road travel-time matrices | BSD 2-Clause (software) |
| [NDMA SACHET](https://sachet.ndma.gov.in) CAP feed (`cap_public_website/rss/rss_india.xml`) | Official Indian disaster alerts (CAP 1.2) | Published by the National Disaster Management Authority, Government of India; see the SACHET portal for terms |
| [USGS Earthquake Hazards](https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php) `all_day` GeoJSON | Earthquake events | U.S. Geological Survey data; public domain unless noted |
| [GDACS](https://www.gdacs.org) event list API | Global disaster events | Global Disaster Alert and Coordination System (UN / European Commission); see gdacs.org for terms of use |

The Lucknow exercise incidents, reports and casualty figures are fictional
(`aegisops/geodata/exercise.py`). Unit counts at each facility are an exercise assumption
(`aegisops/geodata/units.py`); OpenStreetMap only supplies the facility locations. OSM coverage is
incomplete (for example it maps 3 fire stations in the district).

## Documentation

- [API Specification](docs/API.md)
- [Environment variables](ENVIRONMENT.md)
- [Engineering and Research Roadmap](docs/ROADMAP.md)
- [Security Threat Model](docs/SECURITY_THREAT_MODEL.md)
- [Developer Guide](docs/DEVELOPER_GUIDE.md)
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)
- [Two-minute demo script](docs/DEMO.md)
- [Implementation Integrity Analyzer](docs/INTEGRITY_ANALYZER.md)
- Design documents: [SRS](docs/SRS.md), [SAD](docs/SAD.md), [HLD](docs/HLD.md), [LLD](docs/LLD.md),
  [Database](docs/DATABASE_SPECIFICATION.md), [Test Strategy](docs/TEST_STRATEGY.md)
- Research drafts: [Research Proposal](docs/RESEARCH_PROPOSAL.md),
  [Paper draft](docs/IEEE_PAPER_DRAFT.md)

The design documents and research drafts were written in earlier phases. Where they disagree with
this README's Status table, the table and the code are authoritative.
