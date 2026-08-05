# Software Architecture Document (SAD)

## 1. Architectural style

The application uses a layered, ports-and-adapters design. Domain models and policy are independent of HTTP and providers; application ports isolate decision and retrieval implementations; infrastructure supplies the rule-based, retrieval, and NIM adapters; FastAPI supplies transport. The React client is a separate browser consumer.

```text
React console ──HTTP──> FastAPI API ──> DecisionEngine
                              │              ├─ RuleBasedDecisionEngine (default)
                              │              └─ LLMDecisionEngine + RetrievalEngine (optional)
                              │                                  └─ local knowledge/*.md
                              └─ Pydantic validation, role dependency, headers, error handling

SQLAlchemy models + Alembic migration are defined separately; no current API route writes them.
```

## 2. Components and responsibilities

| Component | Responsibility |
| --- | --- |
| `src/` | Vite/React console that calls the versioned API and renders synthetic grid data. |
| `aegisops/domain/` | Strict Pydantic contracts, decision/approval status types, priority scoring, travel-time and safety policy. |
| `aegisops/application/` | Scenario generator and `DecisionEngine`/`RetrievalPort` protocols. |
| `aegisops/infrastructure/` | Deterministic allocator, local FAISS retrieval, NVIDIA NIM client, in-memory audit-log utility. |
| `aegisops/api/` | App factory, routes, schemas, request protection, and development role checks. |
| `aegisops/integrity_analyzer/` | Isolated static-analysis toolkit (source loading, AST parsing, scaffolded-function detection, dict/JSON reports); no dependency on the other `aegisops` layers and no HTTP or CLI surface. |
| `backend/` | ASGI compatibility entry point, legacy route aliases, Alembic configuration, and ORM mappings. |
| `knowledge/` | Local Markdown source corpus searched by the retrieval adapter. |

## 3. Runtime flows

1. `GET /api/v1/scenarios?seed=n` invokes `generate_scenario`; the generator creates six incidents and ten available resources on a 0–100 synthetic grid by default.
2. `POST /api/v1/decisions` validates either a supplied scenario or seed-generated scenario. The default `rule_based` engine produces an advisory. `engine=llm_rag` selects the NIM adapter.
3. The rule engine greedily considers incidents in descending transparent priority, selects nearest available resources of the required type, removes assigned resources from the available set, evaluates safety gates, and returns a `DecisionResult`.
4. The NIM adapter retrieves three text snippets, calls the configured provider with temperature zero, validates returned JSON, and otherwise returns a blocked result. It does not execute tools or external operations.

## 4. Cross-cutting controls

All route input passes Pydantic validation. Decision routes use `require_operator`; production identity is not implemented. Middleware assigns or echoes `X-Request-ID`, adds response security headers, logs request metadata, and returns generic unexpected-error messages. CORS is configured from settings and credentials are disabled.

## 5. Deployment view

The provided Dockerfile installs Python dependencies, copies the backend packages, drops to UID 10001, and serves `backend.main:app` on port 8000. The frontend is built and served separately using Vite tooling. A production deployment needs real authentication, secrets management, persistent audit storage, rate limiting, and operational review before any use beyond synthetic research.
