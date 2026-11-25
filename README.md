# STW Guide

[![CI](https://github.com/Harini-S-1207/prince28-hlt02-stw-guide/actions/workflows/ci.yml/badge.svg)](https://github.com/Harini-S-1207/prince28-hlt02-stw-guide/actions/workflows/ci.yml)
[![Live](https://img.shields.io/website?url=https%3A%2F%2Fstw-guide.onrender.com%2Fhealth&label=live)](https://stw-guide.onrender.com/docs)
[![Uptime (30 days)](https://img.shields.io/uptimerobot/ratio/m804748010-1b5f7c4ada29375720476c1c)](https://stw-guide.onrender.com/health)

**Status:** Week 1 complete · Live at https://stw-guide.onrender.com

**Live Application:** [STW Guide](https://stw-guide.onrender.com) · [API Documentation](https://stw-guide.onrender.com/docs) · [Health](https://stw-guide.onrender.com/health) · [Readiness](https://stw-guide.onrender.com/ready)

---

## Overview

STW Guide is a web-based application designed to help Primary Health Centre (PHC) doctors and medical interns access structured Standard Treatment Workflow (STW) guidance.

The project provides a centralized API for accessing treatment workflow documents, making relevant clinical guidance easier to retrieve.

## Features

- Structured Standard Treatment Workflow records.
- Search and pagination for treatment documents.
- PostgreSQL database with JSONB support.
- FastAPI-based REST API.
- Health and readiness endpoints.
- Database migrations using Alembic.
- Docker-based local development environment.
- Automated CI/CD using GitHub Actions.
- Production deployment on Render.
- LLM Gateway with Gemini as the primary provider and Groq as the fallback.
- OpenAI-compatible provider integration.
- Automatic retries with backoff for retryable provider errors.
- Circuit breaker for handling provider failures.
- Streaming AI chat responses.
- Safe fallback handling without switching providers mid-stream.
- PostgreSQL-based LLM request and usage tracking.
- Token estimation, latency measurement and INR cost estimation.
- Daily LLM usage aggregation.
- Configurable primary and fallback models.

## Technology Stack

| Category | Technology |
|---|---|
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| Vector support | pgvector |
| Cache | Redis |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Validation and settings | Pydantic |
| Package management | uv |
| Testing | Pytest |
| Code quality | Ruff |
| Containerization | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Production hosting | Render |
| Database hosting | Neon |
| AI Integration | Gemini, Groq, OpenAI-compatible API |
| AI Gateway | Custom LLM Gateway |
| Usage Tracking | PostgreSQL |
| AI Testing | FakeLLM, Pytest |

## Project Structure

```text
prince28-hlt02-stw-guide/
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── cd.yml
│
├── data/
│   └── sample_records.json
│
├── docs/
│
├── migrations/
│
├── scripts/
│   ├── load_db.py
│   └── smoke.py
│
├── src/
│   └── stw_guide/
│       ├── api/
│       │   ├── routes/
│       │   │   └── health.py
│       │   └── deps.py
│       ├── db/
│       ├── models/
│       ├── repository/
│       └── config.py
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
└── README.md
```

## Live Application

The application is deployed on Render.

**Production URL:** https://stw-guide.onrender.com

| Endpoint | Description |
|---|---|
| `/docs` | Interactive API documentation |
| `/health` | Liveness check |
| `/ready` | Readiness check with database connectivity |
| `/v1/documents` | Retrieve treatment workflow documents |

## API Endpoints

### Health Check

```http
GET /health
```

Checks whether the application process is alive.

### Readiness Check

```http
GET /ready
```

Checks whether the application is ready to serve requests, including database connectivity.

### List Documents

```http
GET /v1/documents
```

Retrieves treatment workflow documents with pagination.

### Search Documents

```http
GET /v1/documents?q=keyword
```

Searches available documents using a query.

### Retrieve a Document

```http
GET /v1/documents/{document_id}
```

Retrieves a specific treatment workflow document.

For complete API details, visit:

https://stw-guide.onrender.com/docs

---
## AI Gateway Architecture

STW Guide uses a centralized LLM Gateway to communicate with language model providers.

### Provider Configuration

- Primary provider: Gemini.
- Fallback provider: Groq.
- Integration: OpenAI-compatible API.

### Reliability Features

- Automatic retries with backoff for retryable errors.
- Circuit breaker to handle provider failures.
- Automatic fallback when the primary provider fails.
- Configurable request timeout.
- Streaming fallback is allowed only before the first response piece.
- Provider switching is not allowed in the middle of an answer.

### Usage Tracking

Every model call is recorded in PostgreSQL.

Tracked information includes:

- Request ID.
- Provider and model.
- Request status.
- Input and output tokens.
- Latency in milliseconds.
- Estimated cost in INR.
- Fallback usage.
- Request timestamp.

Daily usage information is available through the usage API.

## AI API Endpoints

### AI Chat

POST /v1/chat

Accepts a user question and generates an AI response through the LLM Gateway.

Features:
- Provider selection and fallback.
- Retry handling.
- Streaming response support.
- Usage tracking.

### AI Usage

GET /v1/usage

Provides LLM usage information, including:
- Daily request information.
- Token consumption.
- Latency.
- Estimated cost.
- Provider usage.

## Run Locally in One Command

You need Docker Desktop running. From a fresh clone:

```bash
docker compose up --build
```

This starts Postgres (with pgvector), Redis, runs the migrations and loads the sample data once, then starts the API.

- API docs: http://localhost:8000/docs
- Liveness: http://localhost:8000/health
- Readiness (checks the database): http://localhost:8000/ready

Stop with `Ctrl+C`, then run:

```bash
docker compose down
```

Add `-v` to also delete the database volume.

```bash
docker compose down -v
```

**Warning:** This deletes the local database volume and its stored data.

---

## Develop and Test

| Task | Mac / Linux | Windows |
|---|---|---|
| Run the API with reload | `make dev` | `uv run poe dev` |
| Unit tests (no network) | `make test` | `uv run poe test` |
| Integration tests (needs Docker Compose) | `make test-integration` | `uv run poe test-integration` |
| Coverage report | `make cov` | `uv run poe cov` |
| Lint and format check | `make lint` | `uv run poe lint` |

### Run Without Docker

Install dependencies:

```bash
uv sync --locked
```

Run the development server:

```bash
uv run poe dev
```

Make sure the required database configuration is available before starting the application.

---

## Testing

The project uses Pytest for automated testing.

Test categories:

- Unit tests
- Integration tests
- API endpoint tests
- Database-related tests

Run the complete test and coverage suite:

```bash
uv run poe cov
```

Run lint checks:

```bash
uv run poe lint
```

---

### Day 08 – LLM Gateway Verification

The Day 08 implementation was verified using unit and integration tests.

Tested components:
- LLM Gateway and provider integration.
- Retry and fallback behaviour.
- Circuit breaker behaviour.
- Streaming response behaviour.
- PostgreSQL usage recording.
- Chat and usage API routes.
- Database integration.

Final full-project coverage:

| Metric | Result |
|---|---:|
| Total statements | 1,196 |
| Missed statements | 0 |
| Total branches | 258 |
| Partial branches | 0 |
| Statement coverage | 100% |
| Branch coverage | 100% |

All tests passed in the final verified run.

Two non-fatal dependency warnings were reported.

## CI/CD Pipeline

GitHub Actions automates code validation and production deployment.

### Continuous Integration (CI)

CI runs when code is pushed or a pull request is opened.

It performs:

- Code linting and formatting checks.
- Unit and integration tests.
- Docker image build.
- Publishing the commit-specific Docker image to GitHub Container Registry (GHCR).

### Continuous Deployment (CD)

CD starts automatically after CI succeeds on `main`.

Deployment process:

1. GitHub Actions checks out the merged commit.
2. Database migrations run against Neon.
3. Render receives the exact commit-specific Docker image.
4. The application is deployed.
5. Automated smoke tests verify the live application.

The deployment workflow also supports manual rollback using a specified commit SHA.

---

## Monitoring

Application uptime is monitored using UptimeRobot.

- Monitoring endpoint: `/health`
- Monitoring interval: Every 5 minutes
- Alerts: Email notifications
- Monitor status: https://stw-guide.onrender.com/health

---

## Environment Variables and Secrets

Production secrets are managed securely through GitHub Actions Secrets and Render environment variables.

- DATABASE_URL: Neon PostgreSQL connection.
- RENDER_DEPLOY_HOOK: GitHub Actions Secret.
- APP_ENV: Application environment.
- GIT_SHA: Deployed commit identifier.
- GEMINI_API_KEY: API key for the Gemini provider.
- GROQ_API_KEY: API key for the Groq fallback provider.
- LLM_PRIMARY_MODEL: Configured primary model.
- LLM_FALLBACK_MODEL: Configured fallback model.

API keys must be stored in environment variables or deployment secrets.
Never commit actual API keys to Git.
Never commit credentials or deployment hooks to Git.

---

## Future Improvements

- Expand the Standard Treatment Workflow document collection.
- Improve search and retrieval capabilities.
- Enhance clinical guidance accessibility.
- Improve monitoring and deployment observability.
- Extend automated testing and validation.

---

## Author

**Harini S.**

B.Tech – Artificial Intelligence and Data Science

GitHub: [Harini-S-1207](https://github.com/Harini-S-1207)

---

## License

Add the appropriate project license here if one is selected.
