# CancerJev

CancerJev is a research-only platform for reproducible discovery in freely and
anonymously available public cancer data. Deterministic code owns measurements,
statistics, provenance, and scientific status. Jev will provide bounded semantic
judgment over compact derived state. Research agents will propose explanations and
next tests, but neither Jev nor agents may invent evidence or change scientific
status.

> CancerJev never asks for a GDC token and never uses restricted or controlled
> patient data. It starts with metadata and minimal public processed files. If
> read-level evidence is scientifically necessary and the parent BAM is explicitly
> open, V1 may acquire only a bounded slice. Authorization requirements terminate
> acquisition as `UNAVAILABLE_ACCESS`.

## Repository status

The canonical baseline is `main` at `2bf6c68d93741b9974f46983e0a35c691d69c1f1`
(the restored PR09 hardening state). This repository contains a strong public-data
and durable-resource foundation, but it is **not yet ready to begin CJ-R01–CJ-R33**.
[CJ-R00](docs/plan/cjs/CJ-R00.md) is the mandatory readiness gate.

Implemented and verified in the baseline:

- official GDC-host enforcement, `access=open` filtering, bounded responses, and
  rejection of GDC authentication headers;
- versioned snapshots, frozen identity artifacts, verified source registration,
  canonical public mutation/RNA/CNV/clinical materialization, File/S3 CAS, and
  PostgreSQL resource metadata;
- immutable source/materialization records, cohort membership checks, analysis
  input lineage, audit events, durable jobs, leases, and idempotency;
- initial resource APIs, project/snapshot web screens, deterministic statistical
  primitives, migrations, Docker Compose, and 128 passing tests with PostgreSQL.

Important current limitations:

- durable `run_analysis_from_artifacts` jobs are queued but the statistics worker
  does not claim them;
- the built wheel omits `scientific/`, while source-tree and container layouts hide
  that packaging defect;
- snapshot identity does not hash complete case/sample/aliquot metadata and silently
  collapses conflicting duplicate records;
- Finding identity omits declared input hashes and other scientific identity fields;
- no application authentication/authorization, validation firewall, Jev service,
  SearchRun, ResearchState, evidence graph, or research-agent loop exists;
- the existing GDC transfer wrapper can request complete public files; the canonical
  minimal-transfer planner and bounded open-BAM slicing policy do not exist;
- frontend lint is interactive, dependency audit reports known vulnerabilities,
  and Compose host ports are not isolated.

These are planned facts, not deployed capabilities. See the
[architecture](ARCHITECTURE.md), [product plan](docs/plan/PRODUCT_PLAN.md), and
[canonical roadmap](docs/plan/IMPLEMENTATION_ROADMAP.md).

## Architecture at a glance

```text
official public GDC metadata
        |
        v
DatasetSnapshot -> verified public source -> canonical Materialization
        |                                      |
        +---------- frozen Cohort -------------+
                               |
                         Analysis request
                               |
                 [CJ-R00 must connect execution]
                               v
Finding -> Search/Jev/native research loop -> validation -> researcher handoff
```

Current ownership:

- `packages/gdc`: upstream policy, metadata, identity, transfer, and parsers.
- `packages/resources`: application transactions and resource invariants.
- `packages/database`: PostgreSQL records, repositories, jobs, and leases.
- `packages/storage`: immutable bytes and snapshot publication.
- `packages/schemas`: public and internal data contracts.
- `packages/statistics` and `scientific`: deterministic computation.
- `workers`: background adapters; they do not own scientific truth.
- `apps/api` and `apps/web`: delivery boundaries.

## Canonical plans

- [Product mission and milestones](docs/plan/PRODUCT_PLAN.md)
- [CJ-R00–CJ-R33 implementation roadmap](docs/plan/IMPLEMENTATION_ROADMAP.md)
- [Plain-language guide](docs/plan/PLAIN_LANGUAGE_GUIDE.md)
- [Individual CJ specifications](docs/plan/cjs/README.md)
- [Open-data policy](docs/protocol/open-data-policy.md)
- [Reproducibility contract](docs/reproducibility.md)

The individual CJ specification is authoritative for its scope. A CJ is complete
only when its machine-verifiable acceptance criteria pass; code presence or a green
subset of tests is not completion.

## Local development

Requirements: Python 3.12, Node 22, Docker, Docker Compose, and PostgreSQL 16 for
the complete integration suite.

```bash
python -m venv .venv
# Activate the environment for your shell.
python -m pip install -e '.[dev]'
python -m ruff check .
python -m pytest -q

cd apps/web
npm ci
npm run typecheck
npm run build
```

For database tests, point `CANCERJEV_DATABASE_URL` at a disposable PostgreSQL
database; the suite recreates its public schema. See
[Getting started](docs/getting-started.md) for the safe procedure.

`docker compose up --build` is currently a diagnostic path, not a readiness claim:
CJ-R00 must add build-context exclusions and configurable host ports. Local Compose
credentials are development-only values.

## Verification baseline (2026-09-22)

Executed against restored `main`:

- `python -m ruff check .` — passed.
- `python -m pytest -q` without PostgreSQL — 100 passed, 28 skipped.
- full suite with disposable PostgreSQL 16 — 128 passed, 344 warnings.
- `python -m alembic heads` — one head, `0004`.
- frontend typecheck and production build — passed.
- frontend lint — failed because `next lint` starts an interactive setup prompt.
- `npm audit --omit=dev` — failed with one moderate and one high advisory in the
  installed Next/PostCSS dependency path.
- wheel inspection — failed: `scientific/` is absent.
- `docker compose config --quiet` — passed.
- isolated Compose startup — blocked by hard-coded host port `9000` already in use.

This evidence is recorded in [CJ-R00](docs/plan/cjs/CJ-R00.md). The Python 3.14
audit environment produced pytest-asyncio deprecation warnings; supported CI remains
Python 3.12 until the compatibility matrix is deliberately expanded.

## Safety and scope

CancerJev is for research only and is not a diagnostic or treatment system. Absence
of evidence, unavailable public data, and regions not examined are never converted
into negative molecular observations. Public legal access does not remove the need
for a discovery/validation firewall.
