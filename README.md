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

## Benchmark: Analyzer vs Naive Baseline

The Implementation Integrity Analyzer is evaluated against a labeled corpus of
15 scenarios: 5 true-positive (one seeded integrity failure each), 5 clean
(correctly wired, fully implemented code that must not be flagged), and 5 hard
cases chosen to probe the limits of intra-file static analysis.

The comparison point is a naive grep baseline that checks whether a
safety-critical function name appears anywhere in the file.

| Metric          | Naive Baseline | Analyzer |
| --------------- | -------------- | -------- |
| True positives  | 0              | 5        |
| False positives | 0              | 4        |
| False negatives | 6              | 1        |
| True negatives  | 9              | 5        |
| Precision       | n/a            | 0.556    |
| Recall          | 0.000          | 0.833    |
| MCC             | 0.000          | 0.389    |

MCC is the headline metric: the corpus is small and class-imbalanced, so
accuracy would be misleading.

### Interpretation

The baseline detects nothing (recall 0.000, undefined precision). This is not a
strawman — it is the natural failure mode of string matching. A safety-critical
function's name always appears in its own `def` line, so a text search cannot
distinguish a gate that is *defined* from a gate that is actually *called*.
Separating definition from invocation requires an AST-level call map, which is
what the analyzer builds.

The analyzer resolves all 10 easy scenarios correctly: 5 true positives and 5
clean files with no false alarms. Its errors are concentrated entirely in the 5
hard cases — 4 false positives and 1 false negative — and each corresponds to a
limitation already documented in the module docstrings of `wiring_checker.py`
and `scaffold_detector.py`: no alias resolution, no transitive call resolution
through helpers, no `@abstractmethod` awareness, and no control-flow or ordering
analysis (call-set presence only, not "runs before"). Nothing was excluded,
retuned, or reweighted to improve these numbers.

The error profile skews toward false positives rather than false negatives. For
a safety-critical review tool this is the appropriate bias: a false alarm costs
a developer one review, while a missed integrity violation ships an unguarded
operation.

### Reproducing

## Documentation

- [Phase 1 Foundation](docs/PHASE_1_FOUNDATION.md)
- [API Specification](docs/API.md)
- [Security Threat Model](docs/SECURITY_THREAT_MODEL.md)
- [Engineering and Research Roadmap](docs/ROADMAP.md)
- [Implementation Integrity Analyzer](docs/INTEGRITY_ANALYZER.md)
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
