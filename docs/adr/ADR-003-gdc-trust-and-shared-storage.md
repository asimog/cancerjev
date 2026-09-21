# ADR-003 — Official public GDC authority and shared CAS

**Status:** accepted; current.

## Context

Allowing caller-selected hosts, authentication, mutable live inputs, or service-local
files would undermine access policy and reproducibility.

## Decision

Production GDC traffic uses only `https://api.gdc.cancer.gov`, bounded requests, no
authentication, explicit `access=open`, validated redirects/responses, and frozen
status/release/selection provenance. Missing or non-open access fails closed.

Snapshot artifacts and materialized outputs publish to a shared File/S3-compatible
content-addressed store. PostgreSQL records content hashes and lineage; services do
not assume another container’s local filesystem. Existing snapshot-relative artifacts
remain readable when their original root is mounted, but new publication uses CAS.

The permitted acquisition order is metadata, minimal processed open file, bounded
open-BAM slice, then bounded public-file transfer. V1 prohibits full BAM downloads
and GDC credentials. R04 supplies the complete planner/receipt/slicing contracts.

## Consequences

Availability depends on the official public service and local CAS. Authorization
responses are terminal, not a reason to seek credentials. Production deployment must
restore database and CAS coherently and verify every reference.
