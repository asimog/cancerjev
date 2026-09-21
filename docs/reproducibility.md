# Reproducibility contract

A reproducible CancerJev result binds:

- frozen public source/snapshot and cohort identity;
- exact acquisition receipts and complete/partial artifact manifests;
- source/materialization hashes and canonical schema versions;
- examined coverage and tested universe;
- engine name/version, parameters, eligibility/exclusions, correction family/version;
- relevant runtime/environment identity;
- canonical deterministic outputs.

Jev responses, agent prose, scheduler choices, UI state, timestamps, and retries do not
define scientific identity. They live in separate ledgers and reference the result.

Reproduction uses stored immutable public bytes and exact slice definitions. It never
contacts authenticated GDC, silently substitutes a current release, or widens partial
coverage. Missing inputs produce an explicit unavailable outcome.

Published snapshots, manifests, Findings, locks, and ledger events are immutable.
Correction creates supersession or retraction. CJ-R00 repairs current identity gaps;
CJ-R11 implements the complete reproduction workflow.
