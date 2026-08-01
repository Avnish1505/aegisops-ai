# Test Strategy

## Objective

Verify that the implemented system remains a safe, deterministic, human-gated advisory service. Tests focus on contract validity, allocation invariants, safe failure, retrieval behavior, HTTP behavior, approval-field validation, and ORM mappings. They do not establish suitability for real emergency operations.

## Test layers

| Layer | Coverage |
| --- | --- |
| Domain unit tests | Pydantic bounds and unknown-field rejection, evidence fields, decision approval-state invariants. |
| Decision-engine unit tests | Priority behavior, nearest qualified allocation, unavailable-resource exclusion, no duplicate assignment, unmet demand, and blocked safety gates. |
| Application/infrastructure tests | Seed reproducibility, local retrieval ranking/top-three behavior, NIM JSON validation, retry, missing/unsafe response fallback. |
| API tests | Health probes, scenario and decision contracts, validation errors, request ID/header behavior, engine selection, and operator authorization behavior. |
| Persistence-model tests | ORM creation, relationships, foreign keys, and initial schema assumptions using a test database. |
| Frontend verification | TypeScript production build via `npm run build`; the repository currently has no browser end-to-end test suite. |

## Execution

Create an isolated Python environment, install `requirements-dev.txt`, then run:

```bash
pytest
ruff check .
mypy aegisops backend
npm run build
```

Run the API tests with the configured test settings supplied by the test fixtures. External NVIDIA calls are not made in automated tests; `httpx.MockTransport` is used instead.

## Quality gates

Changes to validation, policy, engines, routes, retrieval, or persistence mappings require the relevant test layer plus the full Python suite. Frontend changes require a production build. Documentation-only changes do not affect executable behavior, but this bundle still runs the existing suite and build as a regression check.

## Known coverage boundaries

There is no load, security penetration, browser E2E, real-provider integration, migration upgrade/downgrade, or production authentication test. These are deliberate gaps to address before any production-oriented use.
