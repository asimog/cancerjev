# ADR-002: versioned GDC parsing and canonical materialization

Status: accepted; architecture approved by the user before implementation.

## Context and problem

PR #7 supplies durable resources, artifact registration, and immutable snapshot
associations. The old ingest prototype assumed upstream TSV columns were canonical,
collected all records in memory, and accepted job-controlled filesystem paths.
This Large change introduces molecular schema v2, explicit parser contracts,
compact resource jobs, and durable scientific lineage.

## Decision and ownership

Keep GDC format parsing, frozen identity resolution, and deterministic normalization
inside `packages/gdc`. Canonical models belong to `packages/schemas`; storage owns
physical objects and Parquet; resource services own transactional registration;
SQL repositories own lookup queries. Workers resolve compact resource identities.

Reuse PR #7 DatasetObject and SnapshotArtifact. Migration 0003 adds immutable source
bindings and materialization lineage rather than a second artifact database.
Physical objects and parser executions have different identities: multiple parser
versions may produce the same bytes, so parser lineage cannot be owned solely by
a physical-hash-keyed DatasetObject row.

Preserve source observations and missingness. Never manufacture mutation identity,
CNV classification, sample identity, or survival endpoints. Reject unknown formats
and ambiguous required identities. Reuse primary-tumor selection while preserving
ties and recording exclusions. Clinical acquisition uses bounded official API pages.

Use explicit Arrow types and bounded Parquet batches. Preserve source record order
and duplicate multiplicity. Separate physical SHA-256, logical row-content SHA-256,
and versioned materialization identity. Publish bytes before transactional registration;
unique lineage IDs reconcile retries and concurrent workers.

## Alternatives

Rejected permissive generic TSV fallback, filename-based identity, first-sample
selection, whole-file molecular lists, online per-gene lookups, molecular database
rows, another object store, and a new downloader. Existing PyArrow, GDC transport,
selection, storage, and PostgreSQL infrastructure suffice without new dependencies.

## Consequences, compatibility, and risks

Molecular schemas move explicitly to v2; logical snapshot identity schemas remain v1.
Legacy arbitrary-path jobs are rejected. Existing snapshot-relative registered
artifacts are read through configured snapshot storage, so PR #7 snapshots need no
rewrite. New sources and outputs use the configured content-addressed File/S3 store.

No cross-store distributed transaction is introduced. Failed database registration
can leave orphan immutable objects; garbage collection remains deferred. Physical
Parquet bytes are not promised stable across library versions. Identity indexes use
memory proportional to frozen cohort metadata; disk staging requires space for the
source and output. Source format variants beyond the exact registry remain unsupported.

PR #9 owns scientific analysis and survival endpoints. PR #14 owns production
molecular acquisition through official gdc-client. See
[the current materialization contract](../architecture/gdc-materialization.md) for
supported metadata tuples, job inputs, hashing, diagnostics, and resource queries.

## Validation

Representative open GDC payloads were acquired and checksum verified; bounded
excerpts and provenance are committed. Parser, actual PostgreSQL artifact flows,
concurrency, rollback, compact worker, legacy snapshot compatibility, clinical
acquisition, and migration roundtrip checks are recorded in
[the PR #8 change report](../changes/pr08-gdc-materialization.md).
