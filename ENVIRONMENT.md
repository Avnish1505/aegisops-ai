# Environment Configuration and Deployment Guide

This document outlines the environment variables and deployment configurations for the AegisOps AI application.

## Environment Variables

Every setting in `aegisops/core/config.py` is read from an `AEGISOPS_`-prefixed environment variable;
names are case-insensitive. Unprefixed names such as `SECRET_KEY` or `DATABASE_URL` are ignored
(`tests/test_config.py`).

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `AEGISOPS_ENVIRONMENT` | Runtime mode. `development` mounts `/api/v1/dev/token`; anything other than `development`/`test` refuses the default key | `production` | No |
| `AEGISOPS_DEBUG` | Enable debug mode (`true` or `false`) | `false` | No |
| `AEGISOPS_CORS_ORIGINS` | Comma-separated list of allowed CORS origins | `http://localhost:3000,http://localhost:5173` | No |
| `AEGISOPS_SECRET_KEY` | HS256 JWT signing key (≥32 bytes) | published development key | Yes, outside development |
| `AEGISOPS_JWT_ALGORITHM` | `HS256` or `RS256` | `HS256` | No |
| `AEGISOPS_JWT_JWKS_URL` | OIDC JWKS URL; required for `RS256` | — | With RS256 |
| `AEGISOPS_JWT_ISSUER` / `AEGISOPS_JWT_AUDIENCE` | Required `iss` / `aud` claims when set | — | No |
| `AEGISOPS_OSRM_URL` | OSRM base URL for road travel times (e.g. `http://osrm:5000`); unset uses straight-line estimates | — | No |
| `AEGISOPS_INGEST_SACHET_RSS_URL` / `AEGISOPS_INGEST_USGS_URL` / `AEGISOPS_INGEST_GDACS_URL` | Feed URLs polled by `python -m aegisops.ingestion.worker` | the public feeds | No |
| `AEGISOPS_INGEST_*_INTERVAL_MIN` | Poll intervals in minutes (SACHET, USGS, GDACS) | 5, 5, 15 | No |
| `AEGISOPS_LLM_API_KEY` (or `NVIDIA_API_KEY`) | Key for the OpenAI-compatible LLM endpoint | — | For live LLM calls |
| `AEGISOPS_LLM_BASE_URL` / `AEGISOPS_LLM_MODEL` | Endpoint and model | NVIDIA NIM, `nvidia/llama-3.1-nemotron-70b-instruct` | No |
| `AEGISOPS_LLM_PRICE_IN_USD_PER_MTOK` / `..._OUT_...` | Prices for cost estimates (reference: OpenRouter Llama-3.3-70B list price, 2026-09-23) | 0.10 / 0.32 | No |
| `AEGISOPS_LLM_CASSETTE_MODE` / `AEGISOPS_LLM_CASSETTE_DIR` | `record` or `replay` LLM HTTP exchanges | `off` | No |
| `AEGISOPS_OTEL_ENDPOINT` (or `OTEL_EXPORTER_OTLP_ENDPOINT`) | OTLP/HTTP base URL for traces (compose: Phoenix at `http://phoenix:6006`) | unset (no export) | No |
| `AEGISOPS_OTEL_SERVICE_NAME` | `service.name` on exported spans | `aegisops-api` | No |
| `AEGISOPS_JWT_ROLE_CLAIM` | Claim holding the role (string or list) | `role` | No |
| `AEGISOPS_RATE_LIMIT` | Rate limit for API endpoints (format: `X/minute` or `X/second`) | `100/minute` | No |
| `AEGISOPS_DATABASE_URL` | Database connection string (SQLite by default) | `sqlite:///./aegisops.db` | No |

### Example `.env` file

```env
AEGISOPS_ENVIRONMENT=production
AEGISOPS_DEBUG=false
AEGISOPS_CORS_ORIGINS=https://example.com,https://app.example.com
AEGISOPS_SECRET_KEY=a_very_strong_secret_key_here
AEGISOPS_RATE_LIMIT=100/minute
AEGISOPS_DATABASE_URL=sqlite:////app/data/aegisops.db
```

## Deployment Configurations

### Docker

The application can be containerized using Docker. A production-ready Dockerfile is provided.

#### Build and Run

```bash
# Build the Docker image
docker build -t aegisops-ai .

# Run the container
docker run -p 8000:8000 \
  -e AEGISOPS_ENVIRONMENT=production \
  -e AEGISOPS_DEBUG=false \
  -e AEGISOPS_SECRET_KEY=your_secret_key_here \
  -e AEGISOPS_RATE_LIMIT=100/minute \
  aegisops-ai
```

### Docker Compose

Run `./scripts/osrm_prepare.sh` once, then `docker compose up --build`: PostgreSQL + PostGIS
(`db`), OSRM (`osrm`; host port 5001, since macOS AirPlay holds 5000), Arize Phoenix for traces
(port 6006), the API (port 8000), the feed worker and the console (port 5173, built by
`Dockerfile.ui`). Put `AEGISOPS_LLM_API_KEY` in `./.env` (gitignored) to enable the LLM steps. The API service migrates, imports facilities from `data/osm`, seeds
the Lucknow exercise and plans it once (`scripts/compose_api_start.sh`). Data lives in the
`pgdata` volume.

```bash
docker compose up --build   # start
docker compose down -v      # stop and delete the database volume
```

### Railway

Deployment to Railway is supported via the `railway.json` configuration.

#### Steps

1. Install the Railway CLI: `npm i -g railway`
2. Login: `railway login`
3. Initialize a new project: `railway init`
4. Deploy: `railway up`

### Vercel

The frontend can be deployed to Vercel using the `vercel.json` configuration.

#### Steps

1. Install the Vercel CLI: `npm i -g vercel`
2. Login: `vercel login`
3. Deploy: `vercel`

## Notes

- Never commit sensitive values (like `AEGISOPS_SECRET_KEY`) to version control. Use environment variables or secret management tools.
- The `.env.example` file provides a template for local development. Copy it to `.env` and adjust as needed.
- In production, ensure that `AEGISOPS_DEBUG` is set to `false` and `AEGISOPS_ENVIRONMENT` is set to `production`.