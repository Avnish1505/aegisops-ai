# API Specification — Phase 1

The canonical interactive OpenAPI definition is served at `/docs` in development only.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health/live` | Process liveness probe |
| GET | `/health/ready` | Application readiness probe |
| GET | `/api/v1/scenarios?seed=42` | Generate a reproducible synthetic scenario |
| POST | `/api/v1/decisions?engine=rule_based` | Produce a human-gated allocation recommendation |

`POST /api/v1/decisions` accepts either a typed `scenario` or a `seed`; omitting both generates a
non-repeatable synthetic scenario. `engine` is `rule_based` by default and may be `llm_rag` for
the optional NVIDIA NIM adapter. Unknown fields are rejected. The route requires an `OPERATOR` or
higher development role token (for example, `Authorization: Bearer operator`); this is not
production authentication. Every response contains `requires_human_approval: true`. `status:
blocked` means a critical requirement is unmet or the NIM adapter safely failed; it is not a
dispatch state.

```json
{"seed": 42}
```

Responses contain `assignments`, `unmet_requirements`, `safety_findings`, `decision_trace`,
`advisory_confidence`, and pending approval fields. Confidence represents allocation coverage only,
not outcome probability. Every response has `X-Request-ID`; callers may supply one for trace
correlation. Unexpected errors use a generic 500 envelope and do not expose internal exception
text. `/health`, `/scenario`, and `/simulate` remain undocumented compatibility aliases.
