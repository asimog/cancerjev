# CJ-R29 — Replicated scheduler and diversity

**Status:** planned; optional distributed program (does not block native production
readiness in CJ-R33). **Owner:** scheduler; ledgers retain authoritative work state.
**Depends on:** R17, R25, R28.

## Mission

Assign identical bounded work to suitable diverse agents, tolerate delivery failure,
and preserve independent results for later convergence.

## Implementation

Match WorkUnit requirements to unexpired capability profiles; reserve quotas; select
diverse agent/provider families; issue replica-specific envelopes around one immutable
EvidencePacket; handle acknowledgement, timeout, retry, cancellation, duplicate and
late delivery; record scheduling rationale and independence metadata.

## Open-data rule

Capabilities contain no controlled-data permission. Every replica receives the same
bounded public packet and cannot acquire extra data, credentials, raw BAMs, or regions.

## Tests and acceptance

Fairness, diversity, identical packet digests, quota races, failover, duplicate/late
results, revocation, stale profiles, and partial outages pass. Scheduler state cannot
change evidence or submission content.
