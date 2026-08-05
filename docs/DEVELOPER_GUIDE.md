# Developer Guide

## Prerequisites

Use Python 3.11–3.13 and a current Node.js/npm installation. The backend dependencies are in `requirements.txt`; development tools are in `requirements-dev.txt`. The frontend package scripts are in `package.json`.

## Local setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
npm install
uvicorn backend.main:app --reload --port 8000
```

In a second terminal, run `npm run dev`. The frontend defaults to `http://localhost:8000` and can be redirected with `VITE_API_BASE_URL`. The API exposes `/docs` only when application debug mode is enabled. See `.env.example` for the repository's development environment variables.

## Working with the API

Decision endpoints require the development role dependency. A bearer token of `operator`, `commander`, or `admin` (optionally prefixed `role:`) meets the implemented check; without a token, development defaults to `VIEWER` and gets 403. This is scaffolding only—do not use it as real authentication.

```bash
curl 'http://localhost:8000/api/v1/scenarios?seed=42'
curl -X POST 'http://localhost:8000/api/v1/decisions?engine=rule_based' \
  -H 'Authorization: Bearer operator' \
  -H 'Content-Type: application/json' \
  -d '{"seed":42}'
```

To exercise the optional provider adapter, set `NVIDIA_API_KEY` and call the same endpoint with `engine=llm_rag`. It retrieves the local knowledge corpus and can block if credentials/provider output are unavailable or invalid. Never commit credentials.

## Project conventions

Keep business policy in `aegisops/domain`, use cases and protocols in `aegisops/application`, adapters in `aegisops/infrastructure`, and HTTP concerns in `aegisops/api`. Add a decision engine through the `DecisionEngine` protocol; it must return a validated `DecisionResult`, require human approval, and not execute external actions. Maintain strict models and extend tests with every behavior change.

`aegisops/integrity_analyzer` is a separate, self-contained static-analysis toolkit (source loading, AST parsing, scaffolded-function detection, and dict/JSON reporting via `aegisops/integrity_analyzer/api.py`). It does not import from or depend on the crisis-response layers above, and it has no HTTP route or CLI entry point.

## Verification and migration commands

```bash
pytest
ruff check .
mypy aegisops backend
npm run build
alembic -c backend/alembic.ini upgrade head
```

The last command applies the defined schema only; it does not enable API persistence. Review the generated database location and use a disposable database when experimenting.
