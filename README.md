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

The restored PR09 baseline is `2bf6c68d93741b9974f46983e0a35c691d69c1f1`.
[CJ-R00](docs/plan/cjs/CJ-R00.md) has repaired and verified that foundation; CJ-R01
is the next planned milestone and has not begun.

Implemented and verified through CJ-R00:

- official GDC-host enforcement, `access=open` filtering, bounded responses, and
  rejection of GDC authentication headers;
- versioned snapshots, frozen identity artifacts, verified source registration,
  canonical public mutation/RNA/CNV/clinical materialization, File/S3 CAS, and
  PostgreSQL resource metadata;
- snapshot identity v2 with complete normalized biological identity and deterministic
  rejection of conflicting duplicate records;
- immutable source/materialization/cohort/Finding records, fenced job attempts,
  terminal recovery, analysis input lineage, audit events, and idempotency;
- artifact-only `cnv_rna` execution from frozen verified inputs through the production
  worker to one server-identified immutable Finding;
- server-owned scientific/result identity, finite-value eligibility, duplicate
  molecular-key rejection, and exact analyzed-population accounting;
- terminal public-access denial and quarantine of complete-file transfer paths;
- reproducible wheel, frontend, image, and isolated Compose gates with split CI jobs.

Important current limitations after CJ-R00:

- no application authentication/authorization, validation firewall, Jev service,
  SearchRun, ResearchState, evidence graph, or research-agent loop exists;
- the canonical minimal-transfer planner and bounded open-BAM slicing contract remain
  assigned to CJ-R04; current code fails closed on complete BAM and quarantines the
  generic complete-file transfer operation;
- only the narrow existing `cnv_rna` artifact execution contract is registered;
- Compose remains a local-development topology, not a production deployment.

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
                 fenced artifact execution
                               |
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
npm run lint
npm run typecheck
npm run build
npm audit --omit=dev
npx playwright install chromium
npm run test:browser
```

For database tests, point `CANCERJEV_DATABASE_URL` at a disposable PostgreSQL
database; the suite recreates its public schema. See
[Getting started](docs/getting-started.md) for the safe procedure.

`docker compose up --build -d --wait` starts the verified local development topology.
Host bindings default to loopback and ports can be isolated with
`CANCERJEV_API_PORT`, `CANCERJEV_WEB_PORT`, `CANCERJEV_MINIO_PORT`, and
`CANCERJEV_MINIO_CONSOLE_PORT`. Local Compose credentials are development-only.

## CJ-R00 verification (2026-09-22)

- Python 3.12.14 with disposable PostgreSQL 16: 176 tests passed; 2 dependency
  deprecation warnings.
- Ruff 0.16.8 passed; Alembic reported the single `0005` head.
- Isolated sdist/wheel build and outside-source-tree runtime imports passed.
- Node 24.13.1/npm 11.8.0: clean install, ESLint, typecheck, Next 16.3.5 production
  build, and production dependency audit passed with zero vulnerabilities.
- One focused Chromium researcher-journey smoke passed with provider I/O intercepted.
- Docker 29.8.0 / Compose 5.5.1 built the images and ran two simultaneous isolated
  projects; both passed API/web health, migration, workers, and cross-service MinIO
  CAS verification.

Full evidence and known limitations are recorded in
[the CJ-R00 change record](docs/changes/cj-r00-readiness.md). Python 3.14 also passed
all 176 tests but emitted the previously known asyncio warnings and a Windows pytest
temporary-directory cleanup warning; supported CI remains Python 3.12.

## Safety and scope

CancerJev is for research only and is not a diagnostic or treatment system. Absence
of evidence, unavailable public data, and regions not examined are never converted
into negative molecular observations. Public legal access does not remove the need
for a discovery/validation firewall.
