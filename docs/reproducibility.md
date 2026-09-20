# Reproducibility

A logical snapshot hash is SHA-256 over UTF-8 JSON serialized with lexicographically sorted object
keys, compact separators, and stable list ordering. The canonical value includes the project, exact GDC
filter, enforced open-access rule, source endpoint, reported release or the explicit
`unknown/not-reported` value, requested fields, full file metadata and checksums, every
file→case→sample→aliquot relationship, all entity IDs, and the transformation, schema, identity-mapping,
selection, and normalization policy versions. Creation time is excluded.

Snapshot publication writes all required artifacts to a sibling staging directory, validates them,
records their SHA-256 values in `COMPLETE.json`, flushes file handles, and atomically renames the complete
directory. An exact repeat verifies and returns the published record without changing `created_at`.
Incomplete, corrupt, or conflicting existing directories fail closed and are never replaced. Legitimately
empty entity tables are schema-bearing zero-row Parquet files; no biological placeholder rows are created.

Materialized bytes are verified by GDC MD5 and size before receiving a SHA-256 content address. Analyses
must record exact eligible case/sample identities, parameters, analysis version and input/result hashes.
Reproduction must create a new execution and compare its result hash; originals are immutable.
