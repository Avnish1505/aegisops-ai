# Engineering and Research Roadmap

## Phase 1 — Foundation (implemented)

Typed domain/API contracts, deterministic baseline, safety gate, human-approval invariant,
reproducible synthetic data, local retrieval, optional NIM adapter with validated blocked fallback,
ORM/migration definitions, tests, Docker runtime, CI quality checks, and the core documentation set.

## Phase 2 — Evidence and human workflow

The server-side operator approval/rejection workflow is implemented: `POST /api/v1/decisions`
persists each decision, and `POST /api/v1/decisions/{id}/disposition` records the operator's
approve/reject action with a reason to an immutable audit log, enforcing that a `blocked` decision
cannot be approved. The operations console now calls this endpoint directly rather than only
holding local state. Remaining for this phase: source provenance surfaced in the UI, a connected
PostgreSQL persistence layer (currently SQLite), production identity/RBAC (currently a development
role token), a read endpoint for decision/approval history, scenario fixtures, and evaluation
dashboards.

## Phase 3 — Constrained AI and simulation

Harden the existing retrieval/NIM prototype with provenance, evaluation, model/prompt versioning,
adversarial prompt-injection testing, and comparison against the deterministic baseline. Add a
constrained multi-agent adapter behind `DecisionEngine` only after those controls. Add a separately
validated simulation engine only after its model assumptions are documented.

## Phase 4 — Production readiness and research publication

Add identity integration, RBAC, secret management, rate limits, observability, deployment IaC,
load/security testing, incident response procedures, cloud deployment guide, literature review,
research proposal, and an IEEE-style paper supported by reproducible experiments.
