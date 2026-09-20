# PR 2: durable resources

## Change

Migration `0002` evolves the foundation schema with durable project metadata, snapshot lifecycle and
artifact references, a first-class artifact registry, deterministic cohort metadata, analysis/job state,
typed Finding indexes, structured immutable audit events, snapshot-artifact roles, and persisted
idempotency outcomes. Migration `0001` remains unchanged.

The API now exposes bounded, stably ordered project, snapshot, artifact, cohort, analysis, and Finding
resources through a transactional service and SQL repository boundary. Snapshot filesystem publication is
followed by idempotent PostgreSQL registration; no filesystem path is exposed as scientific identity.

## Verification and limitations

Unit/contract/scientific tests, Ruff, offline migration generation, and API import checks run locally.
PostgreSQL 16 migration, race, FK, rollback, API, lifecycle, filtering, and idempotency tests run in CI
because the local implementation host has no PostgreSQL or Docker runtime. Genome-scale molecular input
is rejected from metadata payloads. Cross-store garbage collection and full reproduction remain deferred.
