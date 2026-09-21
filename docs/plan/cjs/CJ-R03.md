# CJ-R03 — Lease fencing and terminal recovery

**Status:** planned. **Owner/data:** `packages/database` jobs and Operational Ledger.
**Depends on:** R00–R02.

## Mission and baseline

Guarantee that only the current attempt can publish and that every job reaches an
auditable terminal state. R00 adds attempt-token fencing and exhausted recovery; R03
formalizes cancellation, retry classification, reaping, and operational visibility.

## Implementation

- Require `(job_id, worker_id, attempt_token)` for every transition and heartbeat.
- Close attempts on success, failure, cancellation, expiry, and reclaim.
- Requeue only classified transient failures within budgets; terminally fail
  exhausted jobs and expose stable reason codes.
- Make handler publication idempotent and reject stale completion after lease loss.
- Add reaper metrics, stuck-job queries, and bounded error/redaction rules.

## Open-data rule

GDC authorization and access-policy failures are permanent `UNAVAILABLE_ACCESS`.
Workers never request credentials, change hosts, or turn them into transient retries.

## Tests and acceptance

Use real PostgreSQL concurrency to prove one owner, stale-token rejection, reclaim,
heartbeat races, cancellation, exhaustion, worker death, and exactly-once publication.
Every attempt is explainable and no terminal job remains `claimed` or `running`.
