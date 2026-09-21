# CJ-R11 — Immutable Findings and scientific reproduction

**Status:** planned. **Owner/data:** Finding and reproduction services own Scientific
Ledger records. **Depends on:** R05, R08–R10.

## Mission

Make every accepted Finding immutable, fully identified, reproducible from stored
artifacts, and correctable without mutation.

## Implementation

- Finalize Finding identity over manifest, cohort, engine, parameters, eligibility,
  correction family, environment, coverage, and canonical outputs.
- Add reproduction attempts with expected/actual hashes, field-level mismatch,
  engine availability, logs, and terminal statuses.
- Reproduction loads exact stored bytes and versions; it never silently substitutes
  current code/data. Corrections create superseding/retraction relations.
- Enforce immutability and uniqueness in PostgreSQL, not only services.

## Open-data rule

Replay uses the stored public inputs and exact slice regions/parent identities. It
does not call authenticated GDC or replace unavailable artifacts with new releases.

## Tests and acceptance

Exact replay matches; modified bytes, engine/version drift, missing environment,
partial coverage, unavailable artifacts, and tampering produce explicit outcomes.
Concurrent publication creates one Finding; update/delete is rejected; supersession
preserves history.
