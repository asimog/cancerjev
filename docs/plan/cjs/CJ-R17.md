# CJ-R17 — Shared research work contracts

**Status:** planned. **Owner:** application contracts. **Depends on:** R16.

## Mission

Define one contract set used by native and future external research execution.

## Implementation

Create versioned EvidencePacket, WorkUnit, Submission, Evaluation, capability,
budget, error, and result contracts. Specify size/count/time limits, state transitions,
idempotency, cancellation, provenance, compatibility, and stable rejection codes.
Packets are immutable projections, not database dumps. Native runtime implements the
contracts first; transport remains absent.

## Open-data rule

Packets never contain credentials, raw BAMs, unrestricted matrices, private object
URLs, controlled UUIDs, or acquisition-bypass instructions. They may contain compact
verified summaries and bounded public slice artifacts.

## Tests and acceptance

Round-trip, canonical hash, old/new version, oversize, forbidden field, stale state,
duplicate delivery, cancellation, and redaction tests pass. Independent consumers
interpret the same bounded packet identically without private-module access.
