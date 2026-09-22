# CJ-R13 — Canonical JevService and Semantic Ledger

**Status:** planned. **Owner:** application `JevService`; TypeSafe is one adapter.
**Depends on:** R01, R06, R12.

## Mission

Introduce Jev as bounded semantic judgment without transferring scientific authority
or spreading vendor types through the domain. Jev receives only the compact
CandidateState shortlist, never genome-scale SearchRun output.

## Implementation

- Define application-owned request/answer/error/usage contracts and one async
  TypeSafe adapter with explicit SDK/model/version capture.
- Accept only compact CandidateState assembled from already-gated candidates; never
  accept complete SearchRun result tables, raw matrices, or raw BAM.
- Batch independent typed questions that share one CandidateState into one Jev request
  rather than one request per semantic dimension.
- Persist append-only question set, state hash, resolved model, answers, probability
  distributions, confidence where TypeSafe supplies it, usage, attempts, latency,
  errors, and policy version in the Semantic Ledger.
- Add timeouts, retry classes, circuit behavior, quotas, redaction, and deterministic
  replay/test fakes at the adapter boundary.
- Define no universal confidence threshold in the service. Versioned CancerJev policy
  calibrates thresholds per action on CancerJev evaluation fixtures; Jev failure leaves
  deterministic candidates unchanged.

## Open-data rule

Jev receives compact derived CandidateState, never credentials, raw BAMs, genomic
matrices, complete SearchRun result tables, unrestricted records, or bypass URLs.
Provider failure cannot trigger broader GDC acquisition or authentication.

## Tests and acceptance

Schema, adapter, timeout, retry, rate-limit, cancellation, usage, redaction,
idempotency, provider drift, ledger immutability, batched-question equivalence, and
oversize-state rejection tests pass. No code outside the adapter imports the TypeSafe
SDK; no Jev answer mutates a Finding or p/q value; routing is reproducible without any
global confidence constant.