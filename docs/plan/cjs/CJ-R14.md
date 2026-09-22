# CJ-R14 — CandidateState and explicit Jev modes

**Status:** planned. **Owner:** candidate-state assembler and versioned semantic
policy. **Depends on:** R12–R13.

## Mission

Give Jev a small, typed, reproducible statement of what deterministic code observed
and which semantic task it may perform. CandidateState carries relevant derived
evidence only.

## Implementation

- Define a compact CandidateState containing only relevant derived evidence: candidate
  identity, cohort/cancer, originating SearchRun, originating deterministic
  method/version, effect/statistics, q where applicable, eligible N, missing/excluded
  counts, QC, coverage, related deterministic observations, and limitations. Do not
  overfill it and never attach raw matrices or complete result tables.
- Define separate modes with allowed questions and answer schemas, for example
  pattern classification (choice), coherence (score with a defined rubric), conflict
  (noul), follow-up value (score), and follow-up category (choice), refined to current
  domain terminology. Example classification and follow-up-category options belong to
  registered domain vocabulary, not free text.
- Keep every question atomic: never hide coherence, importance, follow-up, and
  biological mechanism inside one giant question.
- Batch several independent questions that share one CandidateState into one Jev
  request while keeping each answer independently interpretable.
- Hash canonical state and question sets; reject stale or cross-candidate answers.
- Keep policy routing and all thresholds outside provider prompts; no universal
  confidence threshold is defined here.

## Open-data rule

Coverage is explicit: complete processed assay, bounded regional evidence, or
unavailable with reason. Jev is never asked to infer missing, unexamined, or
controlled data.

## Tests and acceptance

Golden state assembly, schema/version changes, redaction, size bounds, missing fields,
stale answers, mode separation, question atomicity, batched-request equivalence,
threshold independence, partial coverage, and deterministic hashes pass. Every answer
references the exact state and cannot claim scientific validation.