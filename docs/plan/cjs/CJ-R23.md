# CJ-R23 — ResearchAction and WorkUnitFactory

**Status:** planned. **Owner:** action registry and factory. **Depends on:** R17, R22.

## Mission

Convert an approved ResearchState intention into a safe, deterministic, budgeted
WorkUnit selected from an allowlisted action catalog.

## Implementation

Define versioned ResearchAction types for metadata inspection, deterministic
analysis, public literature, bounded acquisition, synthesis, and native reasoning.
Each action declares preconditions, inputs, output contract, cost model, coverage
effect, owner, and failure semantics. Factory validates current generation, reserves
budget, resolves immutable references, and emits an idempotent WorkUnit.

## Open-data rule

There is no authenticated-GDC action. Only metadata, registered processed public
artifacts, and bounded open-BAM slices are available. Controlled requirements resolve
to terminal `UNAVAILABLE_ACCESS`.

## Tests and acceptance

Same state/action yields the same WorkUnit; unknown, stale, over-budget, unauthorized,
scope-widening, controlled, and duplicate requests fail predictably. The registry has
no generic shell, URL-fetch, SQL, credential, full-BAM, or arbitrary-slice action.
