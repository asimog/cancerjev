# CancerJev

CancerJev is a reproducible cancer-discovery and scientific-reasoning platform.
It separates three authorities: **Deterministic Science** owns measurements and
scientific evidence; **System One / Jev** will supply bounded semantic judgments;
**Generative Research** will propose hypotheses, mechanisms and experiments.
Semantic and generative output cannot replace deterministic evidence or independently
change scientific status. Research use only; not for diagnosis or treatment.

[The canonical architecture](ARCHITECTURE.md) defines the full pipeline, ownership,
interfaces and implementation boundary.

## Implemented today

- Official NCI GDC REST metadata, open-access-only discovery, bounded pagination,
  status/release capture and reproducible frozen DatasetSnapshots.
- Verified GDC source registration and PR #8 mutation MAF, STAR RNA, gene CNV,
  segment CNV and clinical JSON parsers with immutable materialization lineage.
- PostgreSQL resource metadata, audit records, durable jobs and renewable leases.
- Frozen-graph cohort validation and analysis requests bound to compatible
  snapshot/modality/measurement materializations.
- Safe snapshot-scoped manifests; File/S3 content-addressed storage; shared MinIO
  storage for API, ingest and statistics in Compose.
- Resource APIs, initial project/snapshot UI and deterministic scientific primitives.

The current verified data path is:

```text
 official NCI GDC -> DatasetSnapshot -> verified source -> Materialization
                          |                                  |
                          +------ frozen Cohort + Analysis request
```

## Planned

Artifact-backed analysis/discovery execution, SearchRun and CandidateState gates,
JevService/TypeSafe transport and semantic ledger, reproduction/replication,
distributed research agents and the evidence graph remain planned. The current
statistics worker handles legacy inline jobs and does **not** execute the durable
`run_analysis_from_artifacts` requests. Queuing such a request is not a completed
scientific analysis. No Jev or new scientific engine is introduced here.

Production deployment on Vercel, Railway, Supabase and Cloudflare R2 is a target,
not a claim of deployed infrastructure. Redis, Kafka and Kubernetes are not required.

## Local development

Requires Python 3.12+, Docker Compose and PostgreSQL for durable APIs.

```bash
python -m venv .venv
# Activate the environment for your shell.
pip install -e '.[dev]'
docker compose up --build -d
```

Open the API at `http://localhost:8000/docs` and web at `http://localhost:3000`.
Compose applies migrations and creates one shared MinIO bucket before starting
the API and workers. Its credentials are local development values only.
See [.env.example](.env.example) for standalone runtime settings. S3 uses
`CANCERJEV_OBJECT_BACKEND=s3`, `CANCERJEV_OBJECT_BUCKET` and
`CANCERJEV_OBJECT_ENDPOINT_URL` with the standard AWS credential provider chain.
Keep object settings consistent across services.

## GDC and scientific input contracts

Production authority is `https://api.gdc.cancer.gov`. Every molecular source must
explicitly declare `access=open`; controlled, missing and unknown access fail closed.
There is no GDC token configuration or authenticated acquisition path.
The adapter uses documented `/status`, `/projects`, `/cases`, `/files`,
`/files/versions/{uuids}`, `/history/{uuid}`, `/manifest` and endpoint `_mapping`.
See the [official GDC API guide](https://docs.gdc.cancer.gov/API/Users_Guide/Getting_Started/)
and [metadata/version contracts](https://docs.gdc.cancer.gov/API/Users_Guide/Search_and_Retrieval/).

```text
GET  /v1/gdc/projects?size=20
POST /v1/snapshots/logical                 {"project_id":"TCGA-LUAD"}
POST /v1/snapshots/{snapshot_id}/manifest  {"file_ids":["frozen-file-uuid"]}
POST /v1/cohorts
POST /v1/analyses                         Idempotency-Key required
```

Omit `file_ids` to request all frozen open files. Manifest metadata must still match
the snapshot; live upstream changes cannot silently replace frozen inputs.
Snapshot requests no longer accept `gdc_release`; release provenance comes from
`/status`. Cohort samples must belong to explicitly selected cases in that snapshot.
Each new analysis requires a nonempty `input_materializations` list, for example:

```json
{
  "materialization_id": "sha256:<64 hexadecimal characters>",
  "modality": "expression",
  "measurement_type": "tpm_unstranded"
}
```

Output hashes are resolved from immutable lineage. Optional `expected_input_artifacts`
must exactly match them. Old SHA-only analyses remain readable but are not backfilled.
Bulk transfer remains the official `gdc-client` wrapper; automatic production
download orchestration is not complete.

## Verification

```bash
python -m ruff check .
python -m pytest -q
alembic upgrade head
python scripts/compose_smoke.py --project cancerjev-pr09
```

The integration suite needs `CANCERJEV_DATABASE_URL` pointing to a **disposable**
PostgreSQL database: it recreates the public schema. Without it those tests skip.
The Compose smoke script assumes the selected Compose project is already running.
No static type checker is configured. Exact executed checks and limitations are in
[the PR09 verification record](docs/changes/pr09-architecture-gdc-hardening.md).

## Repository ownership

`apps/` owns API/web boundaries; `packages/gdc/` upstream policy and parsing;
`packages/resources/` transactional operations; `packages/database/` metadata and
jobs; `packages/storage/` immutable bytes; `packages/schemas/` contracts;
`scientific/` and `packages/statistics/` deterministic primitives; `workers/`
background execution. The architectural map and ADRs document the connections.
