# CJ-R15 — Budgeted adaptive discovery

**Status:** planned. **Owner:** discovery orchestrator and policy registry.
**Depends on:** R12–R14.

## Mission

Allow promising candidates to request only registered, bounded deterministic
follow-up analyses.

## Implementation

Define ExpansionRecipe, routing decision, budget reservation, and DiscoveryRun state.
Recipes name an allowlisted engine, frozen inputs, tested scope, expected value,
scientific rationale, and byte/time/compute/semantic/iteration costs. Policy—not Jev—
accepts, rejects, archives, holds, or schedules. Reservations are atomic and replay is
idempotent; every decision enters the ledgers.

## Open-data rule

Recipes cannot request controlled files, credentials, full BAMs, arbitrary URLs,
unregistered engines, unbounded slices, or genes/regions beyond configured scientific
and transfer budgets. Inaccessible needs are recorded, not executed.

## Tests and acceptance

Budget races, loops, stale state, duplicate recipes, provider failure, low-value work,
scope expansion, and exhaustion are tested. The loop terminates deterministically,
all acquired evidence is public/bounded, and routing is reproducible from stored
state, policy, and budgets.
