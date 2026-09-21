# CJ-R24 — HypothesisLock and validation execution

**Status:** planned. **Owner:** validation service and Scientific Ledger.
**Depends on:** R07, R11, R21–R23.

## Mission

Freeze a confirmatory question and execute it against hidden public validation data
without retrospective editing or leakage.

## Implementation

HypothesisLock binds atomic hypothesis/claims, endpoint, direction, cohort,
partition, inputs, method/version, parameters, family, success rule, exclusions, and
coverage. Validation accepts only an intact digest and produces pass/fail/inconclusive/
unavailable with immutable outputs. Replication additionally requires compatible
schema and independent lineage proven before reveal.

## Open-data rule

Validation and replication use public data only. A lock cannot add controlled data;
replication remains unavailable until a compatible independent public dataset exists.

## Tests and acceptance

Any lock mutation changes digest and blocks execution; early reveal, data reuse,
lineage dependence, endpoint switching, family changes, partial overclaims,
restricted substitution, repeated peeking, and concurrent validation are tested. One
lock has one authoritative terminal outcome.
