# CJ-R09 — Cross-modal and defined-group discovery engines

**Status:** planned. **Owner:** deterministic science. **Depends on:** R08.

## Mission and baseline

Replace the current single CNV/RNA primitive with registered, coverage-aware
cross-modal and defined-group engines. R09 owns discovery families D05–D08 of the
[V1 discovery catalogue](../../scientific/discovery-catalogue-v1.md); the existing
`cnv_rna` code is an implementation seed for D06, not the intended whole CancerJev
discovery system.

## Implementation

- **D05 differential expression / defined-group comparison:** compare RNA expression
  between registered biological groups (for example mutant vs wild type, amplified vs
  non-amplified, subtype A vs subtype B). Require explicit group definition, eligible
  population, normalization/method, effect, interval where appropriate, p, q, tested
  gene family, QC, missingness, and coverage.
- **D06 CNV → RNA association:** determine whether copy number associates with RNA
  expression using scientifically registered variants, beginning with same-gene
  CNV → RNA association. Recognize registered convergence (amplified + elevated) and
  registered discordance (amplified + unexpectedly low, or no CNV + extreme
  overexpression) only through deterministic rules. Jev never discovers discordance
  from raw matrices.
- **D07 mutation → RNA association:** test mutation-defined groups against expression
  of the mutated gene and/or a registered genome-wide expression universe; the tested
  universe must be explicit.
- **D08 cohort/subtype enrichment and comparison:** test whether a molecular feature
  differs between registered public cohorts or disease subtypes. Do not combine
  biologically incompatible cohorts simply to increase sample size.
- Define per-engine eligibility, biological alignment, covariate encoding, estimand,
  effect, interval, diagnostic, missingness, family, and failure contracts. Use
  complete cases or an explicitly versioned missing-data method; never silently
  impute. Validate model assumptions and minimum group sizes before significance
  calculations.
- Ordinary mutation–mutation co-occurrence remains D02 in R08; do not duplicate it
  here without a genuinely different covariate-aware model.

## Deferred

Pathway enrichment, unsupervised expression clustering/subtyping, methylation
integration, single-cell, fusion/splice, structural-variant discovery, ATAC, spatial,
cfDNA, and long-read work are explicitly deferred and are not V1 scope.

## Open-data rule

Only public fields in frozen artifacts may become covariates. Missing restricted
covariates stay unavailable. Partial slices cannot create genome-wide negative or
complete-assay classifications.

## Tests and acceptance

Synthetic known-effect/null/confounding fixtures, golden values, duplicate and NaN
handling, small groups, singular models, family correction, partial coverage, and
reordering are tested. Group-definition or normalization changes alter result identity;
incompatible cohorts are rejected; every estimate reports its eligible population,
exclusions, groups, covariates, and coverage.