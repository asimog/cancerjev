# CancerJev

CancerJev is a reproducible cancer-discovery and distributed scientific-reasoning platform. It keeps deterministic measurements and statistics separate from untrusted AI-generated hypotheses, criticisms, and experiment proposals.

> **Research use only. Not for diagnosis or treatment decisions.**

## Current scaffold

This repository starts the first vertical slice in the order defined by the architecture:

1. query open NCI Genomic Data Commons (GDC) metadata;
2. create a canonical, content-addressed logical snapshot;
3. preserve the exact filters and upstream object identifiers needed to reproduce it;
4. expose the operation through a small FastAPI service.

The scaffold uses the GDC REST API directly for metadata and manifests. Bulk object transfer is deliberately delegated to the official [`NCI-GDC/gdc-client`](https://github.com/NCI-GDC/gdc-client); it is not reimplemented here. The GDC frontend and data-model projects are recorded as upstream design references rather than forked application foundations. See [`docs/architecture/technical-architecture.md`](docs/architecture/technical-architecture.md) and [`docs/architecture/upstream-gdc.md`](docs/architecture/upstream-gdc.md).

## Repository layout

```text
apps/api/                    FastAPI boundary
packages/gdc/                GDC REST adapter and filters
packages/schemas/            Canonical, strict domain contracts
packages/provenance/         Deterministic hashing/canonicalization
packages/storage/            Snapshot persistence boundary
workers/ingest/              Logical snapshot orchestration
clients/cancerjev-agent/     Reserved contributor client boundary
scientific/                  Deterministic scientific modules
tests/                       Unit and contract tests
infra/docker/                Local container definitions
docs/                        Architecture and protocols
```

## Local development

Requires Python 3.12+.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest
uvicorn apps.api.main:app --reload
```

Then visit `http://localhost:8000/docs`. A complete local data-plane environment is available with:

```bash
docker compose up --build
```

## First API operations

```text
GET  /health
GET  /v1/gdc/projects?size=20
POST /v1/snapshots/logical
```

The snapshot endpoint accepts a `project_id`, queries only `files.access = open`, and writes an immutable logical snapshot under `CANCERJEV_SNAPSHOT_ROOT` (default: `.data/snapshots`).

