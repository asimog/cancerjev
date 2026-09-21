# CJ-R09 — Cross-modal and covariate-aware engines

**Status:** planned. **Owner:** deterministic science. **Depends on:** R08.

## Mission and baseline

Replace the current single CNV/RNA primitive with registered, coverage-aware
mutation/RNA, CNV/RNA, co-occurrence, cohort-comparison, and confounder engines.

## Implementation

Define per-engine eligibility, biological alignment, covariate encoding, estimand,
effect, interval, diagnostic, missingness, family, and failure contracts. Use complete
cases or an explicitly versioned missing-data method; never silently impute. Persist
the tested universe and coverage scope per modality. Validate model assumptions and
minimum group sizes before significance calculations.

## Open-data rule

Only public fields in frozen artifacts may become covariates. Missing restricted
covariates stay unavailable. Partial slices cannot create genome-wide negative or
complete-assay classifications.

## Tests and acceptance

Synthetic known-effect/null/confounding fixtures, golden values, duplicate and NaN
handling, small groups, singular models, family correction, partial coverage, and
reordering are tested. Identical manifests reproduce; every estimate reports its
eligible population, exclusions, covariates, and coverage.
