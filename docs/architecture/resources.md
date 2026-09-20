# Durable resource layer

```text
API / scientific worker → DurableResourceService → repository contract
                                            ├── PostgreSQL metadata/state
                                            └── immutable artifact reference
```

PostgreSQL owns projects, snapshot metadata, artifact registry entries, deterministic cohorts,
analysis lifecycle, Findings, jobs and attempts, audit events, idempotency outcomes, hashes, and
provenance metadata. It does not own genome-scale RNA, mutation, or CNV rows. Those remain immutable
Parquet or source artifacts in filesystem/S3-compatible object storage.

Repository protocols define the application-facing operations. SQLAlchemy implementations own query
construction, stable ordering, pagination, uniqueness handling, and persistence details. Routes validate
HTTP input and delegate to `DurableResourceService`; they do not issue ad-hoc SQL.

## Identity and lifecycle

Artifact object identity is its verified `sha256:` digest. Registry entries record byte size, media type,
logical role, backend/key, optional GDC UUID/MD5, parser/schema version, row count, and creation time.
Snapshot-to-artifact roles are recorded separately, allowing identical bytes to be reused without copying.
API responses expose object IDs/hashes and metadata, never unrestricted storage keys or filesystem paths.

Cohort identity hashes the snapshot, canonical definition, definition version, sorted membership,
exclusions, and selection-policy version. Database uniqueness is authoritative under races. Analysis
states follow `requested → queued → running → completed|failed|cancelled` with only explicit edges.
Important Finding fields are relational columns while the strict canonical payload remains available.

## Transactions and idempotency

Cohort plus membership metadata, analysis plus job plus audit records, and Finding plus audit record are
committed in one PostgreSQL transaction. Analysis creation reserves `(scope, Idempotency-Key)` before
creating its job. The same key and request hash returns the original analysis; changed input conflicts.

Object storage and PostgreSQL are not a distributed ACID transaction. Snapshot creation first atomically
publishes and verifies immutable artifacts, then registers all metadata in one database transaction. If
registration fails, immutable bytes may be orphaned but never become a partially registered snapshot;
retry reconciles the same hashes and deterministic snapshot identity. Garbage collection of unreferenced
objects is intentionally deferred.

PR 2 records artifact-backed analysis requests but does not make the current row-oriented statistics
worker artifact-aware. Those jobs use `run_analysis_from_artifacts` and remain unclaimed until the
scientific materialization/execution integration is implemented in a later PR.
