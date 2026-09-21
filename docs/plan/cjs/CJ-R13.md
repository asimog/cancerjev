# CJ-R13 — Canonical JevService and Semantic Ledger

**Status:** planned. **Owner:** application `JevService`; TypeSafe is one adapter.
**Depends on:** R01, R06, R12.

## Mission

Introduce Jev as bounded semantic judgment without transferring scientific authority
or spreading vendor types through the domain.

## Implementation

- Define application-owned request/answer/error/usage contracts and one async
  TypeSafe adapter with explicit SDK/model/version capture.
- Persist append-only question set, state hash, resolved model, answers, usage,
  attempts, latency, errors, and policy version in the Semantic Ledger.
- Add timeouts, retry classes, circuit behavior, quotas, redaction, and deterministic
  replay/test fakes at the adapter boundary.
- Jev failure leaves deterministic candidates unchanged.

## Open-data rule

Jev receives compact derived CandidateState, never credentials, raw BAMs, genomic
matrices, unrestricted records, or bypass URLs. Provider failure cannot trigger
broader GDC acquisition or authentication.

## Tests and acceptance

Schema, adapter, timeout, retry, rate-limit, cancellation, usage, redaction,
idempotency, provider drift, and ledger immutability tests pass. No code outside the
adapter imports the TypeSafe SDK; no Jev answer mutates a Finding or p/q value.
