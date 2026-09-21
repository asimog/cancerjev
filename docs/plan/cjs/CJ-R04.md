# CJ-R04 — Minimal public acquisition and materialization

**Status:** planned. **Owner:** acquisition policy in `packages/gdc`; resource service
owns receipts; storage owns bytes. **Depends on:** R02–R03.

## Mission

Acquire the smallest explicitly public evidence that can answer the registered
scientific question.

## Contracts and behavior

Add versioned `OpenDataPolicy`, `AcquisitionPlan`, `BamSliceRequest`, and
`AcquisitionReceipt`. Selection order is metadata, minimal processed open file,
bounded open BAM slice, then bounded public-file transfer. Plans record rationale,
parent identity, expected/actual bytes, limits, hashes, status, and coverage.

BAM requests require a frozen explicitly open parent plus bounded genes or closed
coordinate ranges. Enforce official host, allowed endpoints, maximum genes/regions,
per-region and total span, bytes, response time, redirects, content type, BAM header,
sorted records, parent lineage, and SHA-256. Treat a returned slice as a partial
artifact even if the response is unexpectedly broad.

## Open-data rule

Reject all credentials, authorization headers, cookies, arbitrary URLs, controlled
or unknown parents, full BAMs, whole chromosomes, open-ended/empty ranges, unmapped
reads, and over-budget transfers. A 401/403 becomes terminal `UNAVAILABLE_ACCESS`.

## Tests and acceptance

Contract tests cover planner priority, official unauthenticated slicing, malformed or
oversized responses, redirects, retries, checksums, interruption, idempotency, and
receipt replay. Integration proves no lower-priority transfer occurs when metadata or
a smaller processed file is adequate. No engine is allowed to widen slice scope.
