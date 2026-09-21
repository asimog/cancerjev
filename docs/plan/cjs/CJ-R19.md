# CJ-R19 — Canonical Submission validation

**Status:** planned. **Owner:** shared submission validator. **Depends on:** R16–R18.

## Mission

Create one mandatory boundary that rejects unsafe, malformed, ungrounded, stale, or
scientifically overbroad research submissions before evaluation.

## Implementation

Validate contract version, WorkUnit binding, submitter capability, idempotency,
budgets, entity IDs, atomic claims, evidence references, citations, coverage,
falsifiability, required limitations, and content sizes. Separate structural,
deterministic, semantic, and policy evaluation outcomes with stable reason codes.

## Open-data rule

Reject GDC credentials, authorization headers, controlled UUIDs, unauthorized URLs,
raw BAMs, fabricated access/coverage, and conclusions beyond examined slice scope
before any Jev call or persistence as accepted evidence.

## Tests and acceptance

Positive fixtures pass unchanged. Negative fixtures cover every forbidden access
form, stale work, cross-project references, checksum mismatch, invented citation,
scope widening, injection, oversized content, and duplicate submission. All execution
paths invoke the same validator.
