# CJ-R12 — SearchRun and CandidateObservation

**Status:** planned. **Owner:** discovery service owns search families and candidates.
**Depends on:** R08–R11.

## Mission

Separate exploratory search observations from immutable Findings and make every
multiple-testing family explicit.

## Implementation

Add versioned SearchRun, MultipleTestingFamily, and CandidateObservation models with
snapshot/cohort/input identities, purpose, engine versions, planned/tested/excluded
universes, correction, eligibility, result kind, rank, effect, intervals, flags, and
coverage. Promotion to Finding requires deterministic policy, never Jev preference.

## Open-data rule

The examined universe comes only from eligible public artifacts. Slice searches list
their registered genes/regions; unexamined features are not counted as tested or
negative.

## Tests and acceptance

Known p/q fixtures, family isolation, exclusions, interrupted/replayed search,
ordering, empty/unestimable results, partial coverage, and concurrent completion are
tested. Stored family counts reconcile exactly and no candidate can escape its search
or widen its coverage.
