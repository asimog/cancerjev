# Reproducibility

A logical snapshot hash is computed from canonical project, filter, upstream checksums/UUIDs, identities and transformation version; creation time is excluded. Materialized bytes are verified by GDC MD5 and size before receiving a SHA-256 content address. Analyses must record exact eligible case/sample identities, parameters, analysis version and input/result hashes. Reproduction must create a new execution and compare its result hash; originals are immutable.
