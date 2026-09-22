# CJ-R08 — Public mutation, CNV, and RNA discovery summaries

**Status:** planned. **Owner:** deterministic modality engines. **Depends on:** R04–R07.

## Mission and baseline

Turn existing canonical public mutation, gene/segment CNV, and RNA materializations
into versioned broad-discovery engines with explicit denominators, missingness, and
coverage. R08 owns discovery families D01–D04 of the
[V1 discovery catalogue](../../scientific/discovery-catalogue-v1.md).

## Implementation

- **D01 mutation recurrence:** gene-level mutation frequency and recurrent specific
  variants/hotspots. Persist the tested gene/variant universe, eligible cases, mutated
  cases, denominators, frequency, missing/excluded counts, coverage, QC, and method
  version. Missing mutation data is never equated with wild type.
- **D02 mutation relationships:** co-occurrence and mutual exclusion using explicit
  deterministic statistical methods. Persist the tested pair family, contingency
  counts, eligible N, effect, interval where applicable, p, q, exclusions, missingness,
  and coverage. R09 does not duplicate ordinary mutation–mutation co-occurrence unless
  it performs a genuinely different covariate-aware model.
- **D03 copy-number discovery:** amplification/deletion frequency and recurrent CNV
  segments/regions. Persist the tested universe, eligible samples, affected samples,
  denominators, segment/gene identity, coverage, missing/excluded counts, QC, and
  method version.
- **D04 RNA descriptive discovery:** expression distributions, gene variability, and
  expression outliers. Missing expression is never replaced with zero, and variable
  expression is not automatically treated as biologically meaningful.
- Reuse canonical schemas; reject duplicate biological keys and define aggregation,
  gene normalization, assay eligibility, and exclusion policies.
- Produce complete machine-readable result artifacts for later engines, R12 search
  metadata, and UI read models; R12 owns SearchRun metadata and the deterministic
  candidate gate.
- Persist tested universe, numerator, denominator, eligible IDs, missing/excluded
  counts, QC, method version, input manifest, and coverage class.

## Open-data rule

Prefer minimal public processed outputs. Missing assays, unavailable public files,
and unexamined BAM regions remain missing/not examined; they never become molecular
negatives or zero values.

## Tests and acceptance

Golden and synthetic fixtures cover duplicates, ties, absent assays, partial slices,
gene mappings, empty cohorts, thresholds, ordering, and deterministic hashes. Summary
denominators reconcile with the frozen cohort and every value traces to a verified
public input.