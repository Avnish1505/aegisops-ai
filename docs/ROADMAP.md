# Engineering and Research Roadmap

## Phase 1 — Foundation (implemented)

Typed domain/API contracts, deterministic baseline, safety gate, human-approval invariant,
reproducible synthetic data, local retrieval, optional NIM adapter with validated blocked fallback,
ORM/migration definitions, tests, Docker runtime, CI quality checks, and the core documentation set.

## Phase 2 — Evidence and human workflow

Implement source provenance, a connected PostgreSQL persistence layer, a server-side operator
approval/rejection workflow, production identity/RBAC, immutable decision records, scenario
fixtures, and evaluation dashboards. The existing database models and browser-only disposition are
not this workflow.

## Phase 3 — Constrained AI and simulation

Harden the existing retrieval/NIM prototype with provenance, evaluation, model/prompt versioning,
adversarial prompt-injection testing, and comparison against the deterministic baseline. Add a
constrained multi-agent adapter behind `DecisionEngine` only after those controls. Add a separately
validated simulation engine only after its model assumptions are documented.

## Phase 4 — Production readiness and research publication

Add identity integration, RBAC, secret management, rate limits, observability, deployment IaC,
load/security testing, incident response procedures, cloud deployment guide, literature review,
research proposal, and an IEEE-style paper supported by reproducible experiments.
