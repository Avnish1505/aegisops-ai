# API Specification — Phase 1

The canonical interactive OpenAPI definition is served at `/docs` in development only.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health/live` | Process liveness probe |
| GET | `/health/ready` | Application readiness probe |
| GET | `/api/v1/scenarios?seed=42` | Generate a reproducible synthetic scenario |
| GET | `/api/v1/exercises` | List saved exercises (e.g. the Lucknow monsoon exercise) |
| GET | `/api/v1/alerts?source=&limit=` | Latest ingested hazard alerts (SACHET, USGS, GDACS), without raw payloads |
| GET | `/api/v1/exercises/{id}` | A saved exercise's scenario |
| POST | `/api/v1/decisions?engine=solver` | Produce a verified, human-gated plan (`solver` default; `rule_based`, `llm_rag`) |
| GET | `/api/v1/decisions/{id}` | Read a stored decision (scenario, plan, findings, evidence, approvals) |
| POST | `/api/v1/decisions/{id}/disposition` | Record an approve/reject with a reason |
| GET | `/api/v1/audit/verify` | Walk the hash-chained event log; report the first broken link |

Every location is WGS84 decimal degrees, `{"lat": 26.85, "lon": 80.95}`; resources carry
`speed_kmh`, used only by the straight-line fallback when no road network is available.

`POST /api/v1/decisions` accepts either a typed `scenario` or a `seed`; omitting both generates a
non-repeatable synthetic scenario, plus optional typed `constraints` (`reserve`, `exclude_unit`,
`priority_boost`). `engine` is `solver` (CP-SAT) by default, `rule_based` (greedy baseline) or
`llm_rag` (NVIDIA NIM). Every engine's plan is verified; the response carries `verification`
(verdict and every check), `drafts` (the SITREP), `objective`, `reference_objective`,
`solve_status` and `infeasibility`. Unknown fields are rejected. The route requires a JWT bearer token
whose role is `operator` or higher; the token's `sub` is recorded as the proposer. Approving
requires `approver` or higher and returns 409 `proposer cannot approve` when the approver's `sub`
is the proposer's. In development, `POST /api/v1/dev/token` with `{"sub", "role"}` mints a token. Every response contains `requires_human_approval: true`. `status:
blocked` means a critical requirement is unmet or the NIM adapter safely failed; it is not a
dispatch state.

`GET /api/v1/decisions/{id}` (any role, including `viewer`) returns the persisted record: the
exact input `scenario`, its `scenario_sha256` (SHA-256 of canonical JSON), `assignments`,
`unmet_requirements`, `safety_findings`, `evidence`, `decision_trace`, `prompt_version`,
`model_version`, and every recorded disposition under `approvals`. Rows written before this
migration have `null` for those fields. `tests/test_persistence_integration.py` checks that a stored
scenario replays through the rule-based engine to the same plan.

```json
{"seed": 42}
```

Responses contain `assignments`, `unmet_requirements`, `safety_findings`, `decision_trace`,
`coverage`, and pending approval fields. `coverage` is the share of required units assigned only,
not outcome probability. Every response has `X-Request-ID`; callers may supply one for trace
correlation. Unexpected errors use a generic 500 envelope and do not expose internal exception
text. The prototype aliases `/health`, `/scenario`, and `/simulate` were removed and return 404
(`tests/test_api.py::test_legacy_prototype_routes_are_removed`).
