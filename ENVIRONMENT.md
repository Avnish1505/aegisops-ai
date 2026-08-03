# Environment Configuration and Deployment Guide

This document outlines the environment variables and deployment configurations for the AegisOps AI application.

## Environment Variables

The application uses the following environment variables. Default values are provided where applicable.

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `AEGISOPS_ENVIRONMENT` | Runtime mode (`development`, `staging`, `production`) | `development` | No |
| `AEGISOPS_DEBUG` | Enable debug mode (`true` or `false`) | `true` | No |
| `AEGISOPS_CORS_ORIGINS` | Comma-separated list of allowed CORS origins | `http://localhost:3000,http://localhost:5173` | No |
| `SECRET_KEY` | Secret key for cryptographic operations (e.g., JWT) | `your_secret_key_here` (must be changed in production) | Yes |
| `RATE_LIMIT` | Rate limit for API endpoints (format: `X/minute` or `X/second`) | `100/minute` | No |
| `DATABASE_URL` | Database connection string (SQLite by default) | `sqlite:///./aegisops.db` | No |

### Example `.env` file

```env
AEGISOPS_ENVIRONMENT=production
AEGISOPS_DEBUG=false
AEGISOPS_CORS_ORIGINS=https://example.com,https://app.example.com
SECRET_KEY=a_very_strong_secret_key_here
RATE_LIMIT=100/minute
DATABASE_URL=postgresql://user:password@localhost:5432/aegisops
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
  -e SECRET_KEY=your_secret_key_here \
  -e RATE_LIMIT=100/minute \
  aegisops-ai
```

### Docker Compose

For local development and testing, a `docker-compose.yml` file is provided.

#### Usage

```bash
# Start the services
docker-compose up

# Stop the services
docker-compose down
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

- Never commit sensitive values (like `SECRET_KEY`) to version control. Use environment variables or secret management tools.
- The `.env.example` file provides a template for local development. Copy it to `.env` and adjust as needed.
- In production, ensure that `AEGISOPS_DEBUG` is set to `false` and `AEGISOPS_ENVIRONMENT` is set to `production`.