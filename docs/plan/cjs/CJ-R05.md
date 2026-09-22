# CJ-R05 — Artifact-only scientific execution

**Status:** planned. **Owner:** deterministic execution service; worker is adapter.
**Depends on:** R00, R02–R04.

## Mission and baseline

Execute registered engines only from frozen verified artifacts. R00 connects the
first production worker path; R05 defines the general manifest/registry contract and
eliminates legacy inline scientific input.

## Implementation

- Add `AnalysisInputManifest` with snapshot/cohort, roles, materializations, hashes,
  schema/measurement versions, coverage class, regions, and environment identity.
- Engine registry declares input roles, compatible schemas, complete/partial coverage
  requirements, parameters, outputs, and method version.
- Resolve artifacts through resource/storage contracts into attempt-local paths.
- Disable network during compute; publish verified output artifacts and Findings in
  one idempotent workflow.
- Remove legacy molecular rows from jobs and API schemas.
- Keep the Engine Registry as the single registered scientific-engine mechanism.
  Discovery methods (R08–R12) register there with method versions and contracts; do
  not add a parallel discovery-method or search-definition registry.

## Researcher visibility

Provide a minimal read-only run view over typed API read models sufficient to observe
Analysis -> Job -> worker execution -> deterministic result/Finding locally. This is a
development and local-testing checkpoint, not a dashboard; the browser never
recomputes authoritative scientific values.

## Open-data rule

Inputs must descend from explicitly open acquisition receipts. Slice artifacts are
partial; engines requiring whole-assay coverage reject them before computation.
Execution never contacts live GDC or attempts authenticated substitution.

## Tests and acceptance

Registry/schema mismatch, corrupt/missing bytes, partial-coverage incompatibility,
network access, stale attempt, and duplicate publication fail safely. File and S3
integration produce the same scientific identity. Every supported analysis reaches a
terminal Analysis and immutable Finding using a compact job payload. A minimal
read-only run view exercises Analysis -> Job -> worker -> deterministic result through
typed read models without browser-side scientific computation.
