# AGENTS.md — CancerJev Engineering Rules

This file defines the default engineering rules for AI coding agents working in the CancerJev repository.

These rules apply to every CJ milestone unless the target CJ explicitly states otherwise. A later CJ may refine earlier behavior, but it must not silently weaken established scientific, reproducibility, security, provenance, or public-data invariants.

## 1. Work one CJ at a time

Before coding:

1. Read the target `docs/plan/cjs/CJ-RXX.md`.
2. Read `CJ-R00.md`.
3. Read only the predecessor CJs that materially constrain the target.
4. Read `ARCHITECTURE.md`, relevant ADRs, current implementation, migrations, and tests.
5. Audit current code before proposing changes.
6. Classify each target requirement as:
   - implemented
   - partial
   - missing
   - conflicting
7. Produce an implementation plan before modifying code.

Do not pre-implement later CJ milestones.

Stop when the target CJ acceptance criteria pass.

## 2. Preserve authority boundaries

CancerJev has distinct authorities.

### Deterministic Science

Owns:

- scientific measurements
- eligibility
- tested universes
- statistical calculations
- confidence intervals
- multiple-testing correction
- QC
- scientific identity
- Finding publication
- reproduction and validation outcomes

Deterministic scientific truth must come from versioned deterministic code operating on frozen verified inputs.

### Semantic Judgment

Jev may perform bounded semantic tasks over compact typed state.

Jev must not:

- calculate authoritative statistics
- change p-values or q-values
- redefine cohort membership
- modify Findings
- infer unavailable data
- widen examined coverage
- become scientific authority

### Generative Reasoning

LLMs/research agents may propose:

- mechanisms
- competing hypotheses
- predictions
- falsifiers
- experiments
- literature needs
- next actions

Their output is untrusted until validated by CancerJev contracts and policy.

### Operational State

Jobs, attempts, retries, leases, provider calls, deployments, logs, and incidents are operational state.

Operational state must not redefine scientific truth.

## 3. Preserve dependency direction

Preferred dependency direction:

```text
scientific/domain rules
    ↓
application-owned schemas and services
    ↓
database / storage / GDC / Jev / provider / transport adapters
```

Rules:

- Workers are execution adapters, not owners of scientific rules.
- APIs are delivery boundaries, not scientific authority.
- UI is presentation, not scientific authority.
- Scientific engines must not import provider SDKs.
- Parsers must not open database sessions.
- Provider SDK response types must not leak into domain contracts.
- Agents must not construct raw SQL.
- No module should directly mutate another module's private persistence layout.

## 4. Scientific state distinctions are non-negotiable

Never collapse these states:

- observed positive
- observed negative
- missing
- not acquired
- not examined
- unavailable because controlled
- unavailable because no suitable public source exists
- failed acquisition
- failed computation

In particular:

```text
missing != negative
unavailable != negative
not examined != negative
bounded regional evidence != whole-assay evidence
```

Consensus, Jev output, or model confidence cannot create evidence.

## 5. Public GDC data only

CancerJev uses only freely and anonymously available public GDC data.

Every file must explicitly satisfy:

```text
access=open
```

Missing, unknown, restricted, mixed, or controlled access fails closed.

Never add support for:

- GDC tokens
- `X-Auth-Token`
- GDC `Authorization` headers
- cookies
- token files
- dbGaP credentials
- authenticated retry
- controlled-data UUID acquisition
- alternate production GDC hosts
- complete BAM download
- whole-chromosome slicing
- open-ended genomic ranges
- unmapped-read acquisition
- empty or arbitrary slice scopes
- unbounded BAM slicing

A GDC authorization/access-policy failure is terminal and must not trigger credential seeking or broader acquisition.

Application/service credentials may protect CancerJev infrastructure, but they never authorize GDC data access.

## 6. Current product constraint: no end-user login

CancerJev currently does not require end users to create accounts or log in.

Do not introduce:

- registration
- passwords
- end-user sessions
- user-role systems
- user membership flows

unless a future explicitly approved product decision changes this requirement.

Project/resource isolation, service credentials, quotas, provider budgets, runtime boundaries, and deployment security may still be required without end-user authentication.

## 7. Prefer KISS / DRY / YAGNI / SOLID

Before adding infrastructure, dependencies, frameworks, or abstractions, ask whether the existing architecture can solve the problem cleanly.

Do not add by default:

- Redis
- Kafka
- RabbitMQ
- Kubernetes
- graph databases
- generic workflow engines
- generic agent frameworks
- arbitrary tool executors
- new storage systems
- new authentication frameworks

New infrastructure requires a demonstrated need, not anticipated future scale.

Do not build a generic platform when the CJ requires a narrow CancerJev capability.

## 8. Treat every CJ as a bounded review unit

Recommended branch:

```text
cj-rXX-short-description
```

A CJ may contain multiple small commits, but unrelated cleanup must not be mixed into it.

Before coding, produce a gap matrix:

| Requirement | Current state | Gap | Files | Proof required |
| --- | --- | --- | --- | --- |

Every requirement should map to implementation evidence and tests.

## 9. Implement incrementally

Break each CJ into small logical implementation units.

For each unit:

1. inspect surrounding code
2. add or update focused tests
3. make the smallest coherent change
4. run focused tests
5. fix failures before continuing
6. review the diff

Do not implement a whole CJ as one uncontrolled patch.

## 10. Tests must prove positive, boundary, and negative behavior

Every significant CJ feature should include:

### Positive tests

Prove intended behavior works.

### Boundary tests

Cover cases such as:

- duplicates
- NaN / non-finite values
- empty cohorts
- missing assays
- partial coverage
- stale generations
- old schema versions
- retries
- worker crashes
- malformed provider output

### Negative / adversarial tests

Prove forbidden behavior cannot occur.

Examples:

- controlled GDC access
- auth/token smuggling
- full BAM acquisition
- unbounded slices
- stale worker publication
- duplicate publication
- validation leakage
- fabricated citations
- scope widening
- cross-project disclosure
- unsupported scientific claims

Never weaken a test merely to make an implementation pass.

## 11. Use real PostgreSQL for persistence/concurrency invariants

Mocks are not sufficient proof for:

- `FOR UPDATE SKIP LOCKED`
- lease fencing
- stale-worker rejection
- reaping
- concurrent publication
- transaction races
- uniqueness enforcement
- immutable triggers
- migration behavior

Fast unit tests are useful, but critical database invariants require real PostgreSQL integration tests.

## 12. Job ownership must be fenced

After a job is claimed, later mutations must prove the current attempt.

Preferred ownership identity:

```text
job_id + worker_id + attempt_token
```

The attempt token must be unique per claim.

The current attempt token must be required for operations such as:

- start
- heartbeat
- publish
- succeed
- fail
- cancel where applicable

A stale worker must be unable to publish after lease loss or reclaim.

Expired jobs that have exhausted retries must reach a stable terminal state.

## 13. Scientific inputs are immutable

Scientific execution must use frozen verified artifacts.

Do not put genome-scale molecular matrices into queue payloads.

Prefer compact durable references:

```text
analysis_id
materialization_id
artifact hash
snapshot/cohort identity
```

Execution should resolve and verify authoritative inputs from persistence/storage.

Scientific compute should not contact live GDC.

## 14. Duplicate biological identities must not silently collapse

Never use last-write-wins dictionary behavior as a scientific policy.

For biological identity keys:

- exact allowed duplicates may be canonicalized only by an explicit rule
- conflicting duplicates must fail deterministically
- aggregation requires a versioned scientific rule

This applies to snapshot identity, molecular observations, and scientific engine inputs.

## 15. Eligibility must match the data actually analyzed

Scientific population metadata must reconcile exactly with statistical inputs.

If filtering removes observations because of:

- NaN
- infinity
- missing values
- invalid values
- eligibility policy
- assay availability
- coverage

then eligible counts, IDs, exclusions, and missingness must describe the post-filter population actually analyzed.

Do not compute statistics over one population and report another.

## 16. Scientific identity must be canonical and centralized

Do not let each engine invent ad hoc result hashes.

Scientific identity should bind all material identity-bearing fields required by the relevant CJ, such as:

- frozen snapshot
- cohort
- exact immutable input manifests/hashes
- complete or partial coverage
- examined/tested universe
- engine
- engine version
- parameters
- eligibility policy
- multiple-testing family/version
- relevant environment/runtime identity
- canonical deterministic outputs

Scientific identity normally excludes:

- Jev output
- LLM prose
- scheduler priority
- UI state
- retry count
- timestamps
- worker hostname

Changing an identity-bearing field creates a new result.

## 17. Published scientific records are immutable

Published resources such as Findings must not be edited in place.

Corrections should use explicit relationships such as:

- supersedes
- superseded_by
- retracts
- retracted_by

Critical immutability should be enforced in PostgreSQL as well as application code.

Historical records must remain truthful.

Do not invent missing legacy provenance or silently backfill facts that were never recorded.

## 18. Migrations are part of the feature

For schema changes, update all relevant layers:

- ORM models
- migration
- repositories/services
- API/read models
- fixtures
- unit tests
- integration tests
- migration tests
- compatibility behavior

Do not modify already-landed historical migrations merely to make current code easier unless the repository explicitly treats those migrations as unreleased disposable history.

Prefer new forward migrations.

Where supported, verify downgrade behavior.

## 19. External providers stay behind application-owned adapters

This includes:

- GDC
- S3-compatible storage
- TypeSafe/Jev
- OpenRouter
- literature providers
- future external contributor transports

Domain code should depend on CancerJev-owned contracts.

Provider failure must not silently alter scientific state.

## 20. Structured model output only for authoritative workflows

For Jev/LLM/agent workflows:

- define strict schemas
- validate responses
- reject malformed output
- version state/prompt/policy contracts where relevant
- persist provider/model/version/usage where required
- keep raw prose untrusted

Do not parse important behavior from loosely formatted prose if a typed schema can express it.

## 21. Prompts are not hidden business logic

Do not bury critical rules only inside prompts.

The following belong in versioned application policy/contracts:

- allowed modes
- allowed actions
- thresholds
- budget limits
- state transitions
- coverage rules
- permission boundaries
- rejection behavior

Prompts may communicate those rules to a model, but they are not the authoritative implementation.

## 22. Agent tools must be narrow and allowlisted

Research agents must not receive generic authority such as:

- unrestricted shell
- arbitrary HTTP
- arbitrary SQL
- unrestricted filesystem
- arbitrary GDC regions
- secret access

Expose bounded CancerJev-owned actions instead.

## 23. Keep Evidence Graph implementation simple

An Evidence Graph does not automatically require a graph database.

Authoritative records should remain in the system of record.

Use a deterministic typed projection and existing persistence unless measured requirements justify a new database.

## 24. Validation data must not leak

For hidden validation milestones, test leakage through:

- APIs
- SQL projections
- exports
- logs
- metrics
- debug endpoints
- error messages
- counts
- ordering
- timing where material

Discovery must not infer validation membership or outcomes before a valid lock/reveal.

## 25. UI is derived presentation

The UI may:

- display
- filter
- visualize
- explain
- request supported actions

The UI must not:

- calculate authoritative scientific state
- infer missingness
- reconstruct scientific truth from unrelated endpoints
- mutate Findings
- convert unavailable/not-examined states into negatives

Use typed API read models.

## 26. Version scientific methods explicitly

Changes to scientific behavior may require a new method/version identity.

Examples:

- eligibility rules
- normalization
- estimator/test
- covariates
- threshold
- missing-data method
- multiple-testing family
- coverage interpretation

Do not silently change scientific behavior behind an unchanged method version when reproducibility would be affected.

## 27. Prefer correctness before performance

First establish:

- correct lineage
- correct identity
- correct eligibility
- correct coverage
- deterministic behavior
- tests

Then profile.

Optimize measured hotspots only.

Do not introduce distributed compute because future workloads might be large.

## 28. Distributed execution is optional

Native CancerJev must work correctly without external contributor agents.

Do not make optional distributed-agent infrastructure a prerequisite for core scientific correctness or researcher value.

R28–R32 should remain optional unless the product explicitly decides otherwise.

## 29. Fresh review after every CJ

After implementation:

1. start a fresh review session
2. inspect the complete diff
3. compare it to the target CJ
4. compare it to inherited invariants
5. inspect tests
6. look for:
   - regression
   - scope creep
   - scientific semantic drift
   - security weakening
   - concurrency bugs
   - accidental future-CJ implementation
   - tests that pass without proving the real requirement

Make only targeted fixes after review.

## 30. Swarm / parallel edits

Default:

```text
Swarm OFF
```

for cross-cutting implementation involving:

- database
- migrations
- workers
- scientific identity
- concurrency
- security boundaries
- architecture

Parallel agents are acceptable only for clearly isolated work with non-overlapping ownership, such as read-only audits, independent documentation, or isolated fixtures.

## 31. Required completion evidence

A CJ is not complete because code exists.

Record:

- acceptance commands
- tool/runtime versions where relevant
- test results
- migration results
- build results
- security/policy scan results
- known limitations
- explicit deferrals

Update current-truth documentation when implementation behavior changes.

## 32. Final completion rule

Each CJ should leave CancerJev:

- more correct
- more reproducible
- more explicit
- more testable
- no less secure
- no less scientifically honest

It should not merely make the repository larger.
