# High-Level Design (HLD)

## System context

```text
Operator browser
    │  synthetic scenario / advisory request
    ▼
React operations console ─────> AegisOps FastAPI service
                                      │
                 ┌────────────────────┴───────────────────┐
                 ▼                                        ▼
        Rule-based baseline                     Optional NIM/RAG engine
        (default, deterministic)                local knowledge + NVIDIA API
                 │                                        │
                 └────────────── advisory DecisionResult ┘
                                      │
                                      ▼
                              Human review only
```

## Major interfaces

- Browser to API: JSON over HTTP. The console uses `GET /api/v1/scenarios` and `POST /api/v1/decisions`.
- API to decision engines: `DecisionEngine.recommend(Scenario) -> DecisionResult`.
- NIM engine to retrieval: `RetrievalPort.retrieve(query) -> list[str]`.
- NIM engine to provider: HTTPS chat-completions request when `NVIDIA_API_KEY` is present.
- Persistence: SQLAlchemy mappings and an initial Alembic migration exist but are not attached to a repository, session, or HTTP operation.

## Safety boundary

Every result is advisory and defaults to pending approval. A blocked result is an escalation signal, not an automatic dispatch state. The browser's approve/reject buttons only change React component state; they do not call an approval endpoint or alter backend data. This boundary is intentional and must remain clear in UI, API, and operations documentation.

## Data lifecycle

Scenario data is accepted or generated in memory, used to calculate a response, and returned to the caller. The API does not write it to the database. The local retrieval engine loads all `knowledge/*.md` files into memory while it is constructed. Request metadata is logged; the implementation does not deliberately log the scenario payload.
