# CJ-R14 — CandidateState and explicit Jev modes

**Status:** planned. **Owner:** candidate-state assembler and versioned semantic
policy. **Depends on:** R12–R13.

## Mission

Give Jev a small, typed, reproducible statement of what deterministic code observed
and which semantic task it may perform.

## Implementation

- Define CandidateState with candidate/family identities, effects, intervals,
  missingness, QC, covariates, coverage, citations, prior evaluations, and limitations.
- Define separate modes such as characterize, critique, relevance, evidence relation,
  and expansion triage, each with allowed questions and answer schemas.
- Hash canonical state and question sets; reject stale or cross-candidate answers.
- Keep policy routing outside provider prompts.

## Open-data rule

Coverage is explicit: complete processed assay, bounded regional evidence, or
unavailable with reason. Jev is never asked to infer missing, unexamined, or
controlled data.

## Tests and acceptance

Golden state assembly, schema/version changes, redaction, size bounds, missing fields,
stale answers, mode separation, partial coverage, and deterministic hashes pass. Every
answer references the exact state and cannot claim scientific validation.
