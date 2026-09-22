# CJ-R15 — Budgeted adaptive discovery

**Status:** planned. **Owner:** discovery orchestrator and policy registry.
**Depends on:** R12–R14.

## Mission

Allow promising candidates to request only registered, bounded deterministic
follow-up analyses.

## Implementation

Define ExpansionRecipe, routing decision, budget reservation, and DiscoveryRun state.
The essential flow is:

```text
Candidate
  -> Jev suggests a registered follow-up category
  -> CancerJev policy checks: is the engine/action registered? public data only?
     bounded scope? within acquisition, compute, semantic, and iteration budgets?
  -> allow / reject / hold
  -> schedule an ordinary CancerJev job if allowed
```

Recipes name an allowlisted engine, frozen inputs, tested scope, expected value,
scientific rationale, and byte/time/compute/semantic/iteration costs. Policy—not Jev—
accepts, rejects, archives, holds, or schedules. Reservations are atomic and replay is
idempotent; every decision enters the ledgers.

R15 is bounded policy-driven follow-up, not a workflow or orchestration framework. It
reuses the existing job/lease machinery, must terminate deterministically, and never
creates autonomous unbounded loops.

## Open-data rule

Recipes cannot request controlled files, credentials, full BAMs, arbitrary URLs,
unregistered engines, unbounded slices, or genes/regions beyond configured scientific
and transfer budgets. Follow-up categories are limited to further deterministic
analysis, cross-cohort analysis, verified public literature, and bounded BAM
variant/depth evidence. Inaccessible needs are recorded, not executed.

## Tests and acceptance

Budget races, loops, stale state, duplicate recipes, provider failure, low-value work,
scope expansion, and exhaustion are tested. The loop terminates deterministically,
all acquired evidence is public/bounded, routing is reproducible from stored state,
policy, and budgets, and no unregistered orchestration framework or engine is
introduced.
