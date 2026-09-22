# Getting started

This workflow targets the CJ-R00-verified foundation. CJ-R01 is the next planned
milestone and is not included here.

## Requirements

- Python 3.12
- Node 22 and npm
- Docker and Docker Compose
- PostgreSQL 16 for complete integration tests

## Python

```bash
python -m venv .venv
# Activate the environment for your shell.
python -m pip install -e '.[dev]'
python -m ruff check .
python -m pytest -q
```

Without `CANCERJEV_DATABASE_URL`, PostgreSQL integration tests skip. Use only a
disposable database because the suite recreates the public schema:

```text
CANCERJEV_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/cancerjev_test
```

Do not point tests at development or production data.

## Provider credentials (local live testing)

Local development runs the real application stack. Live TypeSafe Jev integration uses
`TYPESAFE_API_KEY`; later generative reasoning (CJ-R20) uses `OPENROUTER_API_KEY`.
Supply them only as local environment variables and never commit them or place them in
tracked `.env` files. Automated provider tests use deterministic adapter-boundary
fakes; routine CI never calls paid providers or downloads large GDC datasets.

## Web

```bash
cd apps/web
npm ci
npm run lint
npm run typecheck
npm run build
npm audit --omit=dev
npx playwright install chromium
npm run test:browser
```

## Compose

```bash
docker compose config --quiet
docker compose up --build -d --wait
docker compose ps
python scripts/compose_smoke.py --project cancerjev
```

Bindings default to `127.0.0.1`. Override `CANCERJEV_WEB_PORT`,
`CANCERJEV_API_PORT`, `CANCERJEV_MINIO_PORT`, and
`CANCERJEV_MINIO_CONSOLE_PORT` to run isolated projects without port conflicts. For
example, set distinct values before `docker compose --project-name cancerjev-r00-b
up --build -d --wait`. Compose credentials are local-only and must never be reused in
deployment. No GDC token belongs in `.env`.

## Current interfaces

- API health: `GET /health`
- Open GDC projects: `GET /v1/gdc/projects`
- Logical snapshot: `POST /v1/snapshots/logical`
- Snapshot-scoped manifest: `POST /v1/snapshots/{id}/manifest`
- Resource list/get APIs for projects, snapshots, artifacts, cohorts, analyses,
  Findings, and materialization creation

Creating a supported Analysis queues a compact artifact-reference job. The statistics
worker resolves frozen verified inputs and publishes the deterministic Finding through
the resource-owned transaction boundary.
