# CJ-R10 — Versioned survival methods

**Status:** planned. **Owner:** deterministic survival engine. **Depends on:** R05–R09.

## Mission

Deliver scientifically explicit survival analyses rather than generic model calls.

## Implementation

- Version endpoint definitions, time origins, event/censor mapping, eligibility,
  landmark/left-truncation handling, covariates, ties, proportional-hazard checks,
  multiplicity, and reporting.
- Support only predeclared methods such as Kaplan–Meier/log-rank and Cox models when
  their assumptions and sample/event minimums pass.
- Persist event counts, follow-up, exclusions, coefficients/effects, intervals,
  diagnostics, and endpoint field provenance.

## Open-data rule

Use only clinical variables present in public frozen materializations. Never infer,
request credentials for, or represent a restricted/missing endpoint field as tested.

## Tests and acceptance

Reference datasets match expected outputs; censor-only, no-event, tied-time, missing,
small-event, nonproportional, partial-field, and schema-drift cases fail or qualify
honestly. A result names the exact public endpoint fields and method version.
