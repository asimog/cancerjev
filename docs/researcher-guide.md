# Researcher guide

The current UI lists live public TCGA projects and can create a frozen logical
snapshot. The API also exposes durable resource operations, but artifact-backed
analysis execution is disconnected in the restored baseline. Do not interpret a
queued Analysis as a completed scientific result.

Until CJ-R26, use the UI only for source exploration and snapshot creation. Every
result must be read with access, coverage, eligible population, missingness, method,
and provenance. `not examined`, `unavailable`, `not acquired`, and `negative` are
different states.

The planned researcher workflow is described in the
[product plan](plan/PRODUCT_PLAN.md) and [CJ-R26](plan/cjs/CJ-R26.md). CancerJev is
research-only and must not be used for diagnosis or treatment decisions.
