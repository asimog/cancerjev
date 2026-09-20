# System architecture

CancerJev separates real GDC source metadata and immutable objects from canonical Parquet, deterministic statistics, and provenance-backed Findings. PostgreSQL owns mutable metadata and job state; MinIO owns immutable content-addressed objects; analytical matrices remain Parquet and are queried with DuckDB/Polars. Workers claim jobs with `FOR UPDATE SKIP LOCKED`, bounded leases, attempts, and explicit retry decisions. The browser consumes only API data.

Scientific evidence is never created by an LLM. Association is not causation, exploratory structure is not an established subtype, and the application is for research use only.
