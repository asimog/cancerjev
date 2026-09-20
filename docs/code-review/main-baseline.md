# Current-main baseline review

Reviewed 2026-09-20 at `a234c58343fae2a9e36d84d8e7dd498904ed934b` (the checkout's `work` branch points at the current merged main commit).

## What existed

A strict Pydantic identity/snapshot model, paginated open-only GDC file adapter, deterministic snapshot hashing, filesystem snapshot artifacts, manifest generation, basic file/S3 content-addressing, CNV–RNA Pearson analysis with BH correction, Kaplan–Meier summary, FastAPI metadata endpoints, SQLAlchemy model declarations, one Alembic revision, and 13 tests.

## Defects found

* **Snapshot creation was broken against real GDC.** `SnapshotObject.model_validate(hit)` rejected requested raw keys including `analysis`, `cases`, `data_category`, and `experimental_strategy`. A live TCGA-LUAD query returned all of these. Fixed with an explicit transport-to-canonical projection and realistic regression test.
* Both workers were infinite sleep loops. They performed no work, leasing, retries, or persistence.
* The migration called `Base.metadata.create_all`, making history non-auditable.
* PostgreSQL models were unused by the API; there were no jobs, attempts, or cohorts.
* S3 accepted only in-memory bytes and Compose never created its bucket. The configured MinIO `mc ready local` health check referred to an unconfigured alias and was not reliable.
* Molecular schemas existed without parsers or orchestration. Only CNV–RNA was implemented; mutation, CNV frequency, differential expression, Cox/log-rank, clustering, comparison, graph and reproduction were absent.
* No web application existed. API state was filesystem-only and snapshot download paths were the only researcher-facing artifact access.
* The GDC adapter did not enforce an actual streamed response byte ceiling and lacked typed mappings for most declared endpoints.
* `get_projects(size=N)` used N as a page size, then exhausted all projects; its API parameter did not limit results.
* Snapshot provenance omitted software environment, requested fields, derived hashes, and explicit GDC release discovery.
* Identity mapping linked a file to every nested sample in a case. That is conservative/ambiguous but not sufficient evidence of aliquot-level file identity for all GDC data types.
* Empty aliquot output used a synthetic null row, which is not a biological entity.
* The initial test run could not collect because development dependencies were not installed in the base environment. After `pip install -e '.[dev]'`, all 13 baseline tests passed (with Python 3.14 asyncio deprecation warnings).

## Changes in this delivery

The strict boundary regression, streaming file uploads, explicit schema migration, PostgreSQL lease/job state machine, executable workers, canonical delimited-to-Parquet materializer, and first connected Next.js project/snapshot UI were added. Compose now migrates before starting services and initializes MinIO.

## Known gaps (not represented as complete)

This repository still does **not** implement the full V1 requested in the mission: broad molecular format parsing, durable API repositories for every resource, all discovery families, complete Finding persistence/graph/reproduction, all specified visualization surfaces, and the bounded end-to-end live LUAD payload acceptance remain incomplete. These are scientific/product gaps, not hidden behind fabricated data or placeholder buttons.
