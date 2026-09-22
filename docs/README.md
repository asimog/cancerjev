# CancerJev documentation

This directory contains current product, engineering, scientific, and operating
documentation. Historical PR narratives and superseded code-audit snapshots are not
kept here; Git preserves history.

## Sources of truth

- [`../ARCHITECTURE.md`](../ARCHITECTURE.md): current ownership, boundaries, and
  invariants.
- [`plan/PRODUCT_PLAN.md`](plan/PRODUCT_PLAN.md): product mission and milestone exits.
- [`plan/IMPLEMENTATION_ROADMAP.md`](plan/IMPLEMENTATION_ROADMAP.md): ordered CJ map.
- [`plan/cjs/`](plan/cjs/README.md): authoritative individual CJ specifications.
- [`scientific/discovery-catalogue-v1.md`](scientific/discovery-catalogue-v1.md): V1
  deterministic discovery families and their minimum method contracts.
- [`protocol/open-data-policy.md`](protocol/open-data-policy.md): non-negotiable GDC
  and public-data policy.
- [`reproducibility.md`](reproducibility.md): scientific identity and replay rules.
- [`getting-started.md`](getting-started.md): supported local workflow.

ADRs under [`adr/`](adr/) remain active decision records. A merged change updates
current documentation instead of adding a new historical audit directory.
