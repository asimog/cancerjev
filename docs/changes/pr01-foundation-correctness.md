# PR 1: foundation correctness

## Task and architecture

Harden the existing GDC adapter, immutable snapshot publisher, PostgreSQL job queue, database runtime
configuration, and S3 adapter without adding later scientific or agent capabilities. Existing module and
data ownership remains unchanged: GDC owns upstream metadata, snapshot storage owns frozen artifacts,
PostgreSQL owns job state and attempts, and object storage owns content-addressed bytes.

## Implementation

* Added bounded streaming for GDC responses and true caller result limits for projects.
* Expanded canonical snapshot identity to include complete relationships and versioned policies.
* Added typed zero-row Parquet writing, staged atomic publication, artifact hashes, idempotent reuse, and
  corruption rejection.
* Added explicit queue transition and lease checks plus an independent worker heartbeat.
* Unified runtime and Alembic database configuration under `CANCERJEV_DATABASE_URL`.
* Distinguished S3 not-found from permission, service, transport, and other failures.

## Verification

`python -m ruff check .` and the full Python suite pass. Unit and contract coverage includes pagination
limits, chunked oversize responses, snapshot identity/idempotency/failure cleanup/zero rows, queue lease
ownership and retry transitions, configuration resolution, and S3 error classification. Docker was not
available in the implementation environment, so live Compose/PostgreSQL concurrency and MinIO execution
remain unverified locally.

## Scope limits

The official `gdc-client` is still intentionally absent from the runtime image; live bulk payload
acquisition remains PR 9 work. Durable API integration and later V1 science, agent, Jev, graph, and
visualization milestones are unchanged and not claimed complete.
