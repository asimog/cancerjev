# CJ-R08 — Public mutation, CNV, and RNA summaries

**Status:** planned. **Owner:** deterministic modality engines. **Depends on:** R04–R07.

## Mission and baseline

Turn existing canonical public mutation, gene/segment CNV, and RNA materializations
into versioned cohort summaries with explicit denominators, missingness, and coverage.

## Implementation

- Add registered mutation frequency/co-occurrence, CNV frequency/segment, expression
  distribution/outlier, and modality QC summaries.
- Reuse canonical schemas; reject duplicate biological keys and define aggregation,
  gene normalization, assay eligibility, and exclusion policies.
- Persist tested universe, numerator, denominator, eligible IDs, missing/excluded
  counts, QC, method version, input manifest, and coverage class.
- Produce machine-readable summary artifacts for later engines and UI.

## Open-data rule

Prefer minimal public processed outputs. Missing assays, unavailable public files,
and unexamined BAM regions remain missing/not examined; they never become molecular
negatives or zero values.

## Tests and acceptance

Golden and synthetic fixtures cover duplicates, ties, absent assays, partial slices,
gene mappings, empty cohorts, thresholds, ordering, and deterministic hashes. Summary
denominators reconcile with the frozen cohort and every value traces to a verified
public input.
