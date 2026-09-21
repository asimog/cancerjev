# CJ-R30 — Disabled external contributor API and client

**Status:** planned; optional distributed program, disabled by default (does not
block native production readiness in CJ-R33). **Owner:** external transport adapter.
**Depends on:** R19, R25, R28–R29.

## Mission

Expose shared research contracts to approved contributors without giving them domain,
database, object-store, or GDC authority.

## Implementation

Add opt-in scoped contributor keys, WorkUnit lease/poll/ack, bounded artifact exchange,
Submission upload, idempotency, signatures, replay protection, revocation, quotas,
rate limits, audit, and a reference client generated from versioned contracts. Use
pre-signed access only to explicitly packaged bounded objects. Keep server-side
validation identical to native execution.

## Open-data rule

Reject GDC tokens/authorization headers, controlled UUIDs, raw BAMs, arbitrary URLs,
and bypass instructions. Contributor keys authenticate only to CancerJev and can never
authorize server-side GDC access.

## Tests and acceptance

Default deployment exposes no contributor flow. Enable/disable, scope, expiry,
revocation, replay, smuggling, upload size/type, object isolation, contract version,
and native/external parity tests pass. No contributor reaches private infrastructure.
