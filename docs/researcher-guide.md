# Researcher guide

The web application is the real research product and is built incrementally with the
science: a minimal run view at R05, modality result views at R08–R10, discovery,
SearchRun, and candidate views at R12, Jev judgment and bounded follow-up views at
R13–R15, and hypothesis-lock/validation views at R24. CJ-R26 consolidates and hardens
these into the complete cockpit. The UI only presents typed read models; it never
computes or overrides authoritative scientific values.

Until a view exists for what you need, use the API read models directly. A queued or
running Analysis or SearchRun is not a completed scientific result; use only the
immutable published Finding.

Every result must be read with access, coverage, eligible population, missingness,
method, and provenance. `not examined`, `unavailable`, `not acquired`, and `negative`
are different states. The wider discovery model is described in the
[discovery catalogue](scientific/discovery-catalogue-v1.md) and the
[product plan](plan/PRODUCT_PLAN.md). CancerJev is research-only and must not be used
for diagnosis or treatment decisions.