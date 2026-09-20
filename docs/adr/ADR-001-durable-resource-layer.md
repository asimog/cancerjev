# ADR-001: durable resource layer

**Status:** accepted

## Context and problem

The foundation produced immutable snapshot files but API resource identity was still derived from local
paths and PostgreSQL models lacked the contracts needed by later workers and validation stages.

## Decision

Use PostgreSQL as the authoritative owner of resource metadata and lifecycle state behind pragmatic
repository contracts and a transactional application service. Keep scientific bytes in content-addressed
object storage and link them through SHA-256 artifact registry records and snapshot-role associations.
Use deterministic natural identities for snapshots/cohorts and persisted idempotency reservations for
analysis requests.

## Alternatives

Direct SQL in routes was rejected because it duplicates transaction and lifecycle rules. Storing Parquet
or molecular JSON in PostgreSQL was rejected because it violates the analytical-storage boundary. A new
queue or distributed transaction coordinator was rejected as unnecessary for this phase.

## Consequences and risks

Later API and worker work can use stable resource contracts without learning SQLAlchemy internals.
Cross-store writes use publish-then-register reconciliation, so unreferenced immutable objects can remain
after database failure and need later garbage collection. PostgreSQL is required for durable API startup.
