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

`docker compose up` builds and starts the API (http://localhost:8000) and the operations console
(http://localhost:5173, built by `Dockerfile.ui`). On first start the API applies migrations and
records one demo decision for synthetic seed 42 (`backend/seed.py`), readable at
`GET /api/v1/decisions/1`. Data lives in the `aegisops-data` volume.

```bash
docker compose up --build   # start
docker compose down -v      # stop and delete the data volume
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