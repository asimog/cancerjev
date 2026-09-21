# CJ-R32 — Distributed security, load, and failure acceptance

**Status:** planned; optional distributed-program gate (does not block native
production readiness in CJ-R33). **Owner:** security/reliability acceptance.
**Depends on:** R28–R31.

## Mission

Demonstrate that the optional distributed boundary remains secure, bounded, and
recoverable under malicious input, concurrency, overload, and dependency failure.
This gate is required only when distributed execution is enabled; it defines
distributed-release acceptance separate from the native production acceptance in
CJ-R33.

## Required campaigns

Run schema fuzzing; token/header/cookie smuggling; controlled UUID and arbitrary URL
injection; raw/full-BAM and oversized slice requests; fabricated provenance/coverage;
prompt injection; decompression/upload bombs; cross-project object access; replay;
duplicate/late completion; stale leases; provider/storage/database outages; rate-limit
and sustained-load tests. Verify redaction, backpressure, recovery, and invariants.

## Open-data rule

Forbidden requests never reach GDC, Jev, object storage, or accepted evidence.
Authorization failure is terminal and no distributed role broadens access policy.

## Acceptance

Published thresholds for latency, throughput, queue depth, recovery, error rate, and
resource ceilings pass; one valid attempt publishes; logs contain no credentials or
raw genomic payloads; every malicious case has a stable auditable rejection. The
optional distributed program (Milestone E) is incomplete until this gate passes.
