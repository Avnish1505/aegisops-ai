# Software Requirements Specification (SRS)

## 1. Purpose and scope

AegisOps AI is a research and portfolio application for **synthetic** crisis-allocation decision support. It accepts a bounded scenario, generates an advisory allocation, and presents the result for human review. It does not connect to dispatch, contact responders, publish communications, or execute an operational action.

The implemented system includes a React operations console, a FastAPI API, a deterministic allocation engine, an optional NVIDIA NIM-backed advisory engine, local Markdown knowledge retrieval, and SQLAlchemy/Alembic persistence definitions. The HTTP workflow persists each decision, the operator's approve/reject disposition, and a corresponding audit log entry; it does not persist the underlying scenario or its incident/resource records.

## 2. Functional requirements

| ID | Implemented requirement |
| --- | --- |
| FR-01 | The API shall provide live and ready health probes. |
| FR-02 | The API shall generate a synthetic scenario; a supplied non-negative seed shall reproduce the same scenario. |
| FR-03 | A scenario shall contain 1–100 incidents and up to 500 resources, validated against the public model. |
| FR-04 | The rule-based engine shall rank incidents by severity, affected people, and report age; it shall allocate only available, capability-matched resources. |
| FR-05 | A resource shall not be allocated more than once in a recommendation. |
| FR-06 | The result shall state assignments, unmet requirements, safety findings, decision trace, coverage-based advisory confidence, and a human-approval requirement. |
| FR-07 | A critical incident with unmet demand shall produce `blocked`; high-severity unmet demand shall produce a review finding. |
| FR-08 | Decision endpoints shall require at least the `OPERATOR` role. The currently implemented bearer token is a development role token, not production identity verification. |
| FR-09 | The optional `llm_rag` engine shall retrieve up to three local knowledge documents, request JSON from NVIDIA NIM, validate it as a `DecisionResult`, and block after two failed attempts or missing credentials. |
| FR-10 | The web console shall generate and inspect scenarios, request an advisory, display routes/findings/trace, and record the operator's approve/reject disposition (with a reason) to the backend audit log via `POST /api/v1/decisions/{id}/disposition`. |

## 3. Non-functional requirements and constraints

- Inputs reject unknown fields and apply model bounds; invalid input returns a safe 422 envelope.
- Responses receive a request ID and no-store, nosniff, and no-referrer headers. CORS allows configured origins only.
- The baseline is deterministic for a fixed input. Generated scenarios are reproducible when seeded.
- The system uses synthetic grid coordinates, not geographic data, and should not receive real personal or operational data.
- `advisory_confidence` measures allocation coverage only; it is not a probability of success or outcome prediction.
- Docker runs the API as a non-root user. Interactive API documentation is enabled only when debug is true.

## 4. Explicit exclusions

No implemented endpoint creates users, authenticates JWTs, dispatches resources, integrates CAD/911 systems, or guarantees LLM factuality. Decision, approval, and audit persistence exist (`POST /api/v1/decisions` and `POST /api/v1/decisions/{id}/disposition`), but there is no endpoint to list or retrieve past decisions/approvals — read access to decision history is not yet implemented.

## 5. Acceptance evidence

The test suite verifies schema validation, seeded scenario reproducibility, allocation constraints, safety gates, API behavior, retrieval behavior, LLM fallback behavior, approval-field validation, and persistence-model relationships.
