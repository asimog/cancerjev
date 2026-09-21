# CJ-R22 — Scientific synthesis and ResearchState

**Status:** planned. **Owner:** synthesis service. **Depends on:** R21.

## Mission

Build a reproducible state of what is supported, disputed, unknown, unavailable, and
worth testing next from exact ledgers and graph generations.

## Implementation

Define ResearchState generation, candidate/hypothesis status, evidence balances,
unresolved conflicts, coverage, uncertainty, available actions, budgets, and stale
generation checks. Synthesis is versioned deterministic policy over references; model
summaries are annotations, not state authority. Rebuild and diff generations.

## Open-data rule

Represent separately: public available, public not acquired, region not examined,
unavailable controlled, unavailable no suitable public dataset, and failed. Controlled
unavailability never creates an acquisition action.

## Tests and acceptance

State transitions, contradiction, supersession, retraction, stale inputs, partial
coverage, missing sources, deterministic rebuild, and unauthorized project access are
tested. Every state field is explainable through referenced evidence/policy.
