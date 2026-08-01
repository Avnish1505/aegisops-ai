# AegisOps AI — Phase 1 Foundation

## Objective and scope

Phase 1 establishes a safe, reproducible foundation for crisis-intelligence decision support. It
produces advisory allocation recommendations from synthetic incident data; it does not contact
dispatch systems, issue commands, or make autonomous operational decisions.

The initial domain is synthetic multi-incident coordination: medical, fire, structural collapse,
flood, and hazmat incidents. Out of scope are CAD/911 integration, personal data, live feeds, LLM
tool execution, and automatic dispatch. SQLAlchemy/Alembic persistence definitions and an optional
NVIDIA NIM retrieval adapter exist, but the current API does not persist workflow data and the
provider adapter has no operational tools.

## Requirements baseline

1. Validate all scenario input against a typed, versioned contract.
2. Generate repeatable synthetic scenarios from a seed.
3. Allocate only available resources with the requested capability.
4. Explicitly report unmet demand.
5. Block a recommendation with a critical unmet capability.
6. Require authorised human approval for every recommendation.
7. Provide health probes and correlation IDs.

Non-functional requirements are bounded payloads, deterministic behaviour, no scenario-payload
logging, explicit CORS configuration, typed code, tests, and container readiness. Initial targets
are p95 under 250 ms and at most 100 incidents/500 resources per request. These are engineering
targets, not production SLOs.

## Architecture

```text
Operator/UI -> FastAPI transport -> DecisionEngine port -> rule-based baseline
                     |                         |                 |
                validation, errors      NIM/RAG adapter     safety gates
                CORS, request IDs          adapter           + human approval
```

Transport owns HTTP concerns, never allocation policy. The `DecisionEngine` port permits a future
multi-agent adapter to use the identical typed input/output contract. The baseline sorts incidents
by transparent priority and assigns nearest qualified available resources. Complexity is
O(I log I + I × T × R log R): I incidents, T requested resource types, R resources. Spatial
indexing or min-cost flow optimisation is deferred until actual scale/objectives require it.

## Design rationale and research plan

The rule-based engine is a control condition for research and a safe fallback when an AI provider
is unavailable. The implemented NIM adapter uses local retrieval and server-side model validation,
but is still advisory and blocks on missing credentials or invalid output. A global optimiser may
improve aggregate allocation but needs stakeholder-agreed objectives and is a later candidate.

The advisory confidence is allocation coverage, not calibrated outcome probability. A future LLM
adapter must use server-validated structured output, evidence references, policy gates,
model/prompt versioning, and human approval. Evaluate it against this baseline using seed-controlled
and hand-authored scenarios: coverage, response time, invalid allocations, critical-unmet rate,
safety precision/recall, latency, cost, and blinded operator assessment. Retain all seeds,
versions, prompts, and results; synthetic success is not evidence of operational effectiveness.

## Acceptance criteria

- Seeded scenarios are stable at the API contract level.
- Invalid or unknown input returns 422 without internal details.
- Resources are neither double allocated nor allocated while unavailable.
- Critical unmet demand returns `blocked` and requires human approval.
- The service contains no code path that dispatches a resource.
- Tests, linting, and type checks run in CI.
