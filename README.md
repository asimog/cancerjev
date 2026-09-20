# CancerJev

CancerJev is a reproducible cancer-discovery and distributed scientific-reasoning platform. It keeps deterministic measurements and statistics separate from untrusted AI-generated hypotheses, criticisms, and experiment proposals.

> **Research use only. Not for diagnosis or treatment decisions.**

## Deterministic data foundation

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

The snapshot endpoint accepts a `project_id`, queries only `files.access = open`, exhausts pagination,
and writes `snapshot.json`, `manifest.tsv`, identity/coverage Parquet tables, and `provenance.json` under
`CANCERJEV_SNAPSHOT_ROOT`. Bulk transfer is exclusively through the official configurable `gdc-client`.

## Bounded live TCGA-LUAD demonstration

Install the official `gdc-client` first. The metadata snapshot does not download molecular payloads.

```bash
# discover projects
curl 'http://localhost:8000/v1/gdc/projects?size=20'
# create frozen LUAD logical snapshot
curl -sS -X POST http://localhost:8000/v1/snapshots/logical \
  -H 'content-type: application/json' -d '{"project_id":"TCGA-LUAD"}' | tee snapshot.json
# obtain ID, inspect the coverage Parquet file with DuckDB
SNAPSHOT_ID=$(python -c 'import json; print(json.load(open("snapshot.json"))["snapshot_id"])')
curl -o coverage.parquet "http://localhost:8000/v1/snapshots/TCGA-LUAD/$SNAPSHOT_ID/coverage"
duckdb -c "select * from 'coverage.parquet' limit 20"
# materialization primitives (manifest transfer, verification) are library-level and worker-safe
gdc-client download --resume -m ".data/snapshots/TCGA-LUAD/$SNAPSHOT_ID/manifest.tsv" -d .data/cache
pytest tests/scientific/test_crossmodal_golden.py
# verify/reproduce content identity
pytest tests/unit/test_snapshot_service.py
```

Full-project payload transfer can be large; for a bounded live smoke test use a copied manifest containing
its header and a small number of open UUID rows. Never edit `snapshot.json` or call the subset the complete
snapshot. See `docs/architecture/data-foundation.md` for the scientific policy and current scope.
