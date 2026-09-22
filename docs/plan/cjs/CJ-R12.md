# CJ-R12 — SearchRun, deterministic candidate gate, and CandidateObservation

**Status:** planned. **Owner:** discovery service owns registered searches and
deterministic candidates. **Depends on:** R08–R11.

## Mission

Run registered deterministic searches over frozen cohorts, retain complete result
sets, and convert only statistically valid, well-covered results into
CandidateObservations through a method-specific deterministic gate — never through Jev
preference.

## SearchRun

A SearchRun means: run this exact registered method/version over this exact frozen
cohort and tested universe. Record:

- snapshot/cohort identity and input artifact identities;
- engine/method/version and parameters, with purpose;
- planned universe, tested universe, and excluded universe with exclusion reasons;
- multiple-testing family and correction method;
- coverage, status, result artifact identity, candidate count, and scientific
  identity/hash where appropriate.

Compact SearchRun metadata and bounded CandidateObservations live in PostgreSQL.
Complete result tables (for example one row per tested gene) remain immutable
Parquet/CAS artifacts consistent with the existing R05 storage architecture. Tens of
thousands of result rows must not enter job JSON, and the full result table is never
sent to Jev.

## Deterministic candidate gate

The order is fixed:

```text
SearchRun
  -> complete deterministic result set
  -> multiple-testing correction
  -> QC / coverage / eligibility checks
  -> method-specific deterministic candidate gate
  -> CandidateObservation
  -> CandidateState
  -> Jev
```

`CandidateObservation` means: "this deterministic search result qualified as worth
further investigation according to the registered scientific candidate policy." It
must never mean "Jev liked this result."

Candidate rules are method-specific and versioned. There is no universal rule such as
`q < 0.05 = interesting`; interest may depend on statistical significance, effect
magnitude, sample size, event count, group balance, QC, missingness, coverage, and
model diagnostics. The gate is deterministic, reproducible, and independent of Jev.

## Multi-modal convergence

R12 deterministically recognizes when independent analyses implicate the same gene,
region, or biological entity — for example D03 recurrent amplification + D04 RNA
outlier + D06 strong CNV/RNA association + D09 survival association — and may combine
compatible observations into a stronger CandidateObservation/CandidateState.

This first version of convergence is deterministic, bounded orchestration over
compatible search observations. It does not require Jev to notice relationships across
unrelated outputs, and it does not build a graph system; R21 later owns the richer
Evidence Graph.

Candidate ranking/ordering, where present, is deterministic and reproducible from
stored inputs, policy, versioned results, and hashes.

## Open-data rule

The examined universe comes only from eligible public artifacts. Slice searches list
their registered genes/regions; unexamined features are not counted as tested or
negative. Complete result artifacts and candidate counts must reconcile exactly.

## Tests and acceptance

Known p/q fixtures, family isolation, exclusions, interrupted/replayed search,
ordering, empty/unestimable results, partial coverage, and concurrent completion are
tested. Gate boundary fixtures cover pass, fail, and insufficient-coverage outcomes;
no universal threshold exists; convergence combines only compatible observations and
never merges incompatible ones. Stored family counts reconcile exactly and no candidate
can escape its search, widen its coverage, or originate from Jev preference.