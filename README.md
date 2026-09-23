# AegisOps

AegisOps turns messy incident reports into solver-backed response plans that a human approves,
with every number re-checked and every decision replayable. Research platform, not an emergency
system.

That sentence describes where the project is going. The **Status** table below says what exists
today, and every row points to the file or test that backs it.

## Safety position

This service never dispatches resources. Every recommendation has `requires_human_approval: true`,
and a `blocked` recommendation cannot be approved: the API returns 409. It works only on
synthetic scenarios. Do not connect it to emergency operations or use it with real personal or
operational data.

## Quick start

```bash
docker compose up --build
```

This starts the API on http://localhost:8000 and the operations console on http://localhost:5173
(`docker-compose.yml`, `Dockerfile`, `Dockerfile.ui`). On first start the API applies migrations
and records one demo decision for synthetic seed 42 (`backend/seed.py`). You can read it at
http://localhost:8000/api/v1/decisions/1.

Without Docker (Python 3.11–3.13, Node 22):

```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements-dev.txt
alembic -c backend/alembic.ini upgrade head
AEGISOPS_DEBUG=true uvicorn backend.main:app --reload --port 8000
npm ci && npm run dev          # console on http://localhost:5173
```

Settings are read from `AEGISOPS_`-prefixed environment variables (`aegisops/core/config.py`,
[ENVIRONMENT.md](ENVIRONMENT.md)).

## Status

| Area | State | Evidence |
| --- | --- | --- |
| Synthetic scenarios | ✅ The same seed always gives the same scenario | `aegisops/application/scenario_service.py`; `tests/test_api.py::test_scenario_endpoint_is_reproducible_and_sets_request_id` |
| Planning | ✅ CP-SAT assignment minimising severity-weighted travel plus a penalty per unmet unit; typed reserve / exclude / priority constraints; infeasible constraints are named. The greedy engine is kept as a baseline. ⚠️ Travel time is straight-line distance on a synthetic grid | `aegisops/planning/solver.py`; `tests/test_solver.py` |
| Fault injection | ✅ 13 fault classes × 50 seeded scenarios: every injected fault caught by its check (650/650); 0 of 50 clean solver plans falsely blocked. [Report](reports/fault_injection.md) | `tests/fault_injection/`; `scripts/fault_report.py` |
| Safety gates | ✅ An unmet critical requirement blocks the plan | `tests/test_decision_engine.py::test_engine_blocks_critical_unmet_capability` |
| Verification | ✅ Every engine's plan goes through 18 deterministic checks (units, availability, duplicates, capability, quantities, travel times recomputed within max(1 min, 5%), critical coverage, objective vs the CP-SAT optimum, constraints, citations and quotes, SITREP numbers, approval flag, instruction-like report text). Any critical failure blocks; the API returns the full report | `aegisops/verification/verifier.py`; `tests/test_verifier.py`; `tests/test_llm_decision_engine.py` |
| LLM engine (NVIDIA NIM) | ❌ **Not evaluated against a live model.** Every test uses a mocked HTTP response. Without `NVIDIA_API_KEY` it returns `blocked` | `tests/test_llm_decision_engine.py`; `tests/test_api.py::test_decision_endpoint_selects_llm_rag_engine` |
| Retrieval | ⚠️ **Keyword hashing, not semantic search.** Tokens are hashed into 256 buckets and ranked by inner product | `aegisops/infrastructure/knowledge_retrieval.py`; `tests/test_knowledge_retrieval.py` |
| Human decision | ✅ Approve/reject with a reason, written to an audit log. Blocked decisions return 409 | `tests/test_persistence_integration.py::test_blocked_decision_cannot_be_approved_or_create_disposition` |
| Proposer ≠ approver | ❌ Not enforced yet; an `operator` can approve a decision they created | `aegisops/api/app.py` (`create_disposition`) |
| Decision record | ✅ Stores the input scenario and its SHA-256, the plan, verification report, SITREP, constraints, travel matrix, and prompt/model versions. A stored record replays and re-verifies to the same result | `tests/test_persistence_integration.py::test_stored_decision_replays_and_reverifies_to_the_same_result` |
| Audit log integrity | ✅ Decisions, verifications and dispositions append to a hash-chained `events` table; each event also hashes the decision/approval row it created. `GET /api/v1/audit/verify` reports the first broken link, and editing any event column, deleting an event, or editing a decision or approval row is detected. ⚠️ Deleting the newest event is only detectable against an externally kept `head_hash` | `aegisops/audit/event_log.py`; `tests/test_event_chain.py` |
| Auth | ⚠️ **Development only.** The bearer token *is* the role name (`viewer`, `operator`, `approver`, `admin`) | `aegisops/api/security.py`; `tests/test_roles.py` |
| Free-text intake / message drafting | ❌ No LLM intake or drafting. ⚠️ A deterministic SITREP template is generated and its numbers verified | `aegisops/communication/sitrep.py` |
| Multi-agent | ❌ None. `backend/agents/roles.py` holds data-only role descriptions | `backend/agents/roles.py` |
| Database | ⚠️ SQLite is the only backend exercised by tests and the container | `tests/test_persistence_integration.py`; `Dockerfile` |
| Evaluation | ✅ Golden-scenario regression suite for the rule-based engine | `sim/evaluation_harness.py`; `tests/test_evaluation_harness.py` |
| Delivery | ✅ CI runs Python lint/types/tests (3.11), frontend lint/typecheck/build, and a container smoke test that requires 200 from `/health/ready` and a seeded `POST /api/v1/decisions` | `.github/workflows/ci.yml` |
| Logging | ✅ JSON logs carry an ISO-8601 UTC `timestamp`, `level`, and `request_id` | `tests/test_observability.py::test_json_log_record_has_real_timestamp_and_level` |

## Architecture

```text
browser console (src/) -> FastAPI (aegisops/api) -> DecisionEngine -> verify (domain/policy.py)
                                  |                   rule_based | llm_rag (NIM, re-checked)
                                  +-> SQLite: decisions, approvals, audit_log (backend/db)
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

## Documentation

- [API Specification](docs/API.md)
- [Environment variables](ENVIRONMENT.md)
- [Engineering and Research Roadmap](docs/ROADMAP.md)
- [Security Threat Model](docs/SECURITY_THREAT_MODEL.md)
- [Developer Guide](docs/DEVELOPER_GUIDE.md)
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)
- [Implementation Integrity Analyzer](docs/INTEGRITY_ANALYZER.md)
- Design documents: [SRS](docs/SRS.md), [SAD](docs/SAD.md), [HLD](docs/HLD.md), [LLD](docs/LLD.md),
  [Database](docs/DATABASE_SPECIFICATION.md), [Test Strategy](docs/TEST_STRATEGY.md)
- Research drafts: [Research Proposal](docs/RESEARCH_PROPOSAL.md),
  [Paper draft](docs/IEEE_PAPER_DRAFT.md)

The design documents and research drafts were written in earlier phases. Where they disagree with
this README's Status table, the table and the code are authoritative.
