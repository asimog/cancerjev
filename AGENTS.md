# AGENTS.md — CancerJev

Repository-wide rules for coding agents working on CancerJev.

## 1. Start from the target requirement

For CJ work:

1. Read the target `CJ-RXX.md`.
2. Inspect the code and tests directly relevant to it.
3. Read predecessor CJs, `CJ-R00.md`, ADRs, or broader architecture docs only when they materially constrain the target or are explicitly referenced.
4. Audit current behavior before editing.
5. Identify what is implemented, partial, incorrect, or missing.
6. Make a concrete implementation plan before changing code.

Do not pre-implement unrelated future CJs.

Do not assume existing tests prove the CJ is correctly implemented.

## 2. Implement the correct solution

The goal is not the smallest patch.

Implement the simplest robust architecture that:

* fully satisfies the target requirement
* preserves valid existing behavior
* fits the existing architecture
* is maintainable and testable
* avoids unnecessary complexity
* does not introduce unrelated functionality

If the existing design is wrong for the requirement, fix the design rather than layering workarounds over it.

Do not preserve a bad abstraction merely because it already exists.

## 3. Scientific authority

Authoritative scientific truth must come from deterministic, versioned CancerJev code operating on identified and verified inputs.

Jev may perform bounded semantic judgment but must not:

* calculate authoritative statistics
* alter p-values or q-values
* redefine cohort membership
* change tested populations
* modify Findings
* manufacture unavailable evidence
* expand examined coverage

LLMs may propose hypotheses, explanations, experiments, falsifiers, literature needs, and next actions.

LLM/Jev output is not authoritative scientific truth unless accepted through explicit deterministic CancerJev logic.

Workers execute work.

APIs expose behavior.

UI presents behavior.

None of them should independently own scientific rules.

## 4. Preserve scientific states

Never collapse:

```text
missing != negative
unavailable != negative
not acquired != negative
not examined != negative
failed != negative
bounded evidence != whole-assay evidence
```

Absence of evidence, model confidence, or semantic consensus cannot create evidence.

Reported eligibility, counts, exclusions, and missingness must describe the population actually analyzed.

## 5. Scientific identity and history

Scientific execution must use frozen or explicitly identified inputs.

Reproducibility-relevant scientific behavior must have deterministic, centralized identity/versioning.

Do not silently change scientific behavior behind an unchanged method/version identity.

Do not silently rewrite published Findings or equivalent scientific records.

Corrections must use explicit replacement, supersession, retraction, or versioning semantics where required.

Duplicate biological identities must never silently use last-write-wins behavior.

## 6. GDC policy

CancerJev uses anonymously accessible public GDC data only.

Require:

```text
access=open
```

Fail closed for unknown, missing, mixed, restricted, or controlled access.

Never add:

* GDC authentication or tokens
* credential discovery
* authenticated retry
* controlled-data acquisition
* complete BAM downloads
* whole-chromosome acquisition
* unbounded or arbitrary genomic slicing

Access-policy failures must not trigger attempts to obtain credentials or broaden acquisition.

## 7. Architecture boundaries

Prefer:

```text
scientific/domain logic
        ↓
application-owned services/contracts
        ↓
database / storage / GDC / Jev / provider / transport adapters
```

Provider SDK types should not leak into domain contracts.

Workers should call application/domain behavior rather than reimplement it.

Parsers should not own persistence.

APIs should not contain authoritative scientific logic.

UI should display authoritative state rather than recreate it.

Critical rules belong in code/contracts, not only in prompts.

## 8. PostgreSQL and concurrency

Use real PostgreSQL when correctness depends on PostgreSQL behavior, including:

* locking
* transaction races
* concurrency
* `FOR UPDATE SKIP LOCKED`
* leases and attempt ownership
* stale-worker rejection
* uniqueness constraints
* triggers
* migrations

A stale worker must not be able to publish or mutate state after losing ownership.

Do not require PostgreSQL merely because production eventually persists a result.

## 9. Testing strategy

Tests must prove behavior, not merely execute code.

Use the cheapest test layer that genuinely proves the requirement.

Prefer fast tests for:

* deterministic scientific calculations
* eligibility and coverage
* statistics
* hashing/identity
* validation
* duplicate handling
* policy logic
* serialization
* routing
* provider-response mapping

Use PostgreSQL/integration tests only when real persistence or multi-component behavior matters.

Never weaken a valid test merely to make implementation pass.

## 10. Fast development loop

Do not run the entire repository suite after every edit.

Use:

```text
edit
→ smallest affected test
→ fix failure
→ rerun failures
→ related fast tests
→ required PostgreSQL/integration tests
→ continue
```

Run a focused test:

```bash
python -m pytest path/to/test.py::test_name -q -x
```

Rerun recent failures:

```bash
python -m pytest --lf -q
```

Run fast tests:

```bash
python -m pytest -m "not postgres and not integration and not slow" -q
```

Run PostgreSQL tests only when required:

```bash
python -m pytest -m postgres -q
```

Run integration tests only when required:

```bash
python -m pytest -m integration -q
```

If only a few tests fail, rerun those tests first.

Do not repeatedly rerun a whole slow integration file while debugging one failure.

## 11. Database test performance

Ordinary DB tests should not recreate the schema and replay all migrations for every test.

Where practical:

```text
initialize disposable DB
→ apply migrations once
→ isolate test with transaction/savepoint or targeted cleanup
→ rollback/reset
```

Migration tests may create clean schemas when testing migration behavior itself.

Do not add parallel test execution until shared-database safety and the actual bottleneck are understood.

## 12. Slow or hanging tests

If a focused test that should normally finish quickly runs for several minutes:

1. stop it
2. identify the exact test
3. rerun it with `-vv`
4. inspect for:

   * database locks
   * blocked transactions
   * repeated migrations
   * network waits
   * hanging workers/subprocesses
   * Docker/service waits
   * oversized fixtures
   * repeated artifact generation

Profile before optimizing:

```bash
python -m pytest --durations=30 -q
```

Routine automated tests must not depend on live external services unless explicitly designated as live/manual integration tests.

## 13. Migrations and providers

For schema changes, update all affected layers: models, migrations, repositories/services, read models, fixtures, and tests.

Prefer forward migrations.

Do not rewrite landed migration history unless the repository explicitly treats it as disposable.

External providers must remain behind CancerJev-owned interfaces.

Provider failure must not silently change scientific meaning.

Structured provider/model output must be validated before authoritative use.

## 14. Completion

Before declaring a CJ complete:

1. Compare the implementation against every acceptance criterion.
2. Review the complete diff.
3. Check for unintended scope creep or regression.
4. Run relevant focused tests.
5. Run required PostgreSQL/integration tests.
6. Run applicable lint, typecheck, build, migration, and policy/security checks.
7. Run the broader regression suite once.
8. Record known limitations and explicit deferrals.

Passing tests alone does not prove completion if the tests do not prove the actual requirement.

Do not declare completion while known acceptance criteria remain unimplemented.