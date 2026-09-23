# API Specification — Phase 1

The canonical interactive OpenAPI definition is served at `/docs` in development only.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health/live` | Process liveness probe |
| GET | `/health/ready` | Application readiness probe |
| GET | `/api/v1/scenarios?seed=42` | Generate a reproducible synthetic scenario |
| POST | `/api/v1/decisions?engine=rule_based` | Produce a human-gated allocation recommendation |
| GET | `/api/v1/decisions/{id}` | Read a stored decision (scenario, plan, findings, evidence, approvals) |
| POST | `/api/v1/decisions/{id}/disposition` | Record an approve/reject with a reason |

`POST /api/v1/decisions` accepts either a typed `scenario` or a `seed`; omitting both generates a
non-repeatable synthetic scenario. `engine` is `rule_based` by default and may be `llm_rag` for
the optional NVIDIA NIM adapter. Unknown fields are rejected. The route requires an `OPERATOR` or
higher development role token (for example, `Authorization: Bearer operator`); this is not
production authentication. Every response contains `requires_human_approval: true`. `status:
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
