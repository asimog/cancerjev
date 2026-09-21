# Getting started

This workflow targets restored `main`. It runs the current foundation; CJ-R00 must
pass before roadmap feature implementation begins.

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

## Web

```bash
cd apps/web
npm ci
npm run typecheck
npm run build
```

At the audited baseline, `npm run lint` is interactive and the dependency audit has
known findings; CJ-R00 must repair both before they are green gates.

## Compose

```bash
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

The current file uses fixed host ports 3000, 8000, 9000, and 9001. Check for conflicts
first; R00 makes them configurable. Compose credentials are local-only and must never
be reused in deployment. No GDC token belongs in `.env`.

## Current interfaces

- API health: `GET /health`
- Open GDC projects: `GET /v1/gdc/projects`
- Logical snapshot: `POST /v1/snapshots/logical`
- Snapshot-scoped manifest: `POST /v1/snapshots/{id}/manifest`
- Resource list/get APIs for projects, snapshots, artifacts, cohorts, analyses,
  Findings, and materialization creation

Creating an Analysis currently queues a disconnected artifact job; it does not prove
scientific completion until CJ-R00 connects the production worker path.
