# AegisOps AI

**Multi-Agent Crisis Intelligence & Decision Support Platform**

AegisOps AI is being engineered as a human-supervised crisis decision-support platform. Phase 1
delivers the secure, reproducible backend foundation: typed scenario contracts, deterministic
resource-allocation baseline, safety gates, audit-friendly decision traces, and delivery tooling.
It is a research and portfolio platform, not an emergency dispatch system.

## Safety position

This service never dispatches resources. Every recommendation has `requires_human_approval: true`.
`blocked` means a critical capability is unmet and escalation is mandatory. Do not connect it to
emergency operations or use it with real personal or operational data.

## Quick start

Requires Python 3.11–3.13.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
export AEGISOPS_DEBUG=true
uvicorn backend.main:app --reload --port 8000
```

In another terminal:

```bash
curl 'http://localhost:8000/api/v1/scenarios?seed=42'
curl -X POST http://localhost:8000/api/v1/decisions \
  -H 'Content-Type: application/json' \
  -d '{"seed": 42}'
pytest
```

Development documentation is available at `http://localhost:8000/docs` when `AEGISOPS_DEBUG=true`.
Explicitly configure browser origins with `AEGISOPS_CORS_ORIGINS`; the local default permits only
the common development UI origins.

## Architecture

```text
HTTP client -> FastAPI API -> typed DecisionEngine port -> deterministic baseline
                    |                   |                  |
             validation/CORS/IDs   future LLM adapter   safety + human gate
```

The baseline is intentionally not an LLM. It provides an interpretable, repeatable control
condition for later multi-agent research. A future agent adapter must remain behind the same port
and cannot bypass validation, safety policy, evaluation, or human approval.

## Repository layout

- `aegisops/domain` — validated entities and transparent decision policies.
- `aegisops/application` — use cases and ports.
- `aegisops/infrastructure` — the deterministic baseline adapter.
- `aegisops/api` — FastAPI transport, safe error handling, CORS, and observability headers.
- `aegisops/integrity_analyzer` — isolated static-analysis toolkit (source loading, AST parsing,
  scaffolded-function detection, and structured dict/JSON reports).
- `backend` and `sim` — migration-compatible prototype entry points.
- `tests` — unit and API acceptance tests.
- `docs` — Phase 1 architecture, API, and security artifacts.

## Documentation

- [Phase 1 Foundation](docs/PHASE_1_FOUNDATION.md)
- [API Specification](docs/API.md)
- [Security Threat Model](docs/SECURITY_THREAT_MODEL.md)
- [Engineering and Research Roadmap](docs/ROADMAP.md)
- [Software Requirements Specification](docs/SRS.md)
- [Software Architecture Document](docs/SAD.md)
- [High-Level Design](docs/HLD.md)
- [Low-Level Design](docs/LLD.md)
- [Database Specification](docs/DATABASE_SPECIFICATION.md)
- [Test Strategy](docs/TEST_STRATEGY.md)
- [Developer Guide](docs/DEVELOPER_GUIDE.md)
- [User Manual](docs/USER_MANUAL.md)
- [Incident Response Runbook](docs/INCIDENT_RESPONSE_RUNBOOK.md)
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)
- [Research Proposal](docs/RESEARCH_PROPOSAL.md)
- [IEEE-Style Paper Draft](docs/IEEE_PAPER_DRAFT.md)

## Delivery

`Dockerfile` runs the backend as a non-root user. GitHub Actions runs tests, Ruff, and mypy for
Python 3.11 and 3.12. Before public deployment, add authenticated access, role-based approval
workflows, persistent signed audit logs, gateway rate limiting, secret management, monitoring, and
formal safety/security review.
