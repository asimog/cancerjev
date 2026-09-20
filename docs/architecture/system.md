# System architecture

CancerJev separates real GDC source metadata and immutable objects from canonical Parquet, deterministic statistics, and provenance-backed Findings. PostgreSQL owns mutable metadata and job state; MinIO owns immutable content-addressed objects; analytical matrices remain Parquet and are queried with DuckDB/Polars. Workers claim jobs with `FOR UPDATE SKIP LOCKED`, bounded leases, attempts, and explicit retry decisions. A dedicated heartbeat thread renews a healthy running lease through an independent database session; ownership and unexpired lease checks guard every transition, and expired attempts remain auditable when reclaimed. The browser consumes only API data.

`CANCERJEV_DATABASE_URL` is the runtime source of truth for API settings, workers, Alembic, integration tests, and Compose. Alembic's checked-in URL is only a local tooling fallback. Credentials must not be logged. S3 existence checks return false only for actual not-found responses; permission, transport, and service failures remain errors.

Durable resource requests follow `API → DurableResourceService → repository → PostgreSQL`. Snapshot
artifacts are registered by verified SHA-256 and linked by logical role; storage paths and unrestricted
object keys are not public resource identity. See `docs/architecture/resources.md`.

Scientific evidence is never created by an LLM. Association is not causation, exploratory structure is not an established subtype, and the application is for research use only.
