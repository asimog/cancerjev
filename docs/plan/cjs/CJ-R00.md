# CJ-R00 — Restored-main readiness gate

**Status:** required before CJ-R01

**Baseline:** `2bf6c68d93741b9974f46983e0a35c691d69c1f1`

**Classification:** large cross-cutting correctness repair

**Governing rules:** [`AGENTS.md`](../../AGENTS.md) defines the default engineering
rules for this milestone. This file may tighten them but never weaken them. In
particular, R00 introduces no end-user login, registration, sessions, or user roles;
the API remains local-development-only until CJ-R06 introduces runtime isolation.

## Mission

Make the restored PR09 codebase a reproducible, secure, scientifically coherent
starting point for CJ-R01–CJ-R33. R00 repairs existing contracts; it does not import
discarded Milestone A/B code or pre-implement later roadmap features.

## Verified audit findings

### Blockers

1. `DurableResourceService.create_analysis()` queues
   `run_analysis_from_artifacts`, while `workers/statistics/__main__.py` claims only
   `run_analysis` and `reproduce_finding`. Durable analyses cannot execute.
2. The Hatch wheel includes `apps`, `packages`, and `workers`, but omits
   `scientific`. Wheel inspection confirmed the omission; source and Docker layouts
   mask it.
3. Snapshot hashing stores full file/link records but only case/sample/aliquot IDs.
   Conflicting duplicate biological records are silently collapsed by dictionary
   comprehensions.
4. CNV/RNA analysis silently overwrites duplicate rows by tuple key. Finding
   `result_hash` excludes declared input hashes and material scientific identity.
5. Lease ownership uses worker ID without a per-attempt fencing token. Exhausted
   expired attempts can remain nonterminal because claim selection excludes them.
6. The transfer wrapper supports complete file download and has no canonical
   metadata-first acquisition plan or BAM-slice contract.
7. `persist_finding()` accepts caller-supplied Finding IDs, result hashes, versions,
   and payloads after checking only that an Analysis is completed; the deterministic
   execution owner does not recompute or attest the identity at publication.
8. Database immutability protects artifacts, audit events, published snapshots,
   sources, materializations, snapshot links, and selected Analysis input fields, but
   Cohort and Finding rows have no equivalent update/delete trigger.

### Quality and operational risks

- `npm run lint` launches interactive Next.js setup and fails as an automated gate.
- `npm audit --omit=dev` reports one high and one moderate advisory in the installed
  Next/PostCSS path; remediation requires deliberate compatibility review.
- There is no root or web `.dockerignore`; local caches made the first build context
  exceed 427 MB before cancellation.
- Compose hard-codes host ports; isolated startup failed because port 9000 was in use.
- CI tests Python/PostgreSQL only; it omits wheel inspection, frontend, image,
  Compose, migration round-trip, token-policy scan, and browser gates.
- The API has no application authorization boundary and must remain explicitly
  local-development-only until CJ-R06 introduces runtime isolation.
- Python 3.14 produced 344 pytest-asyncio/SQLAlchemy warnings and a Windows temp
  cleanup error. Supported CI is Python 3.12; compatibility expansion is separate.

### Verified strengths to preserve

- Official GDC host, open-only filters, response limits, redirect/auth-header
  rejection, and frozen manifest validation.
- Canonical public mutation/RNA/CNV/clinical parsers with verified input bytes and
  bounded row batches.
- PostgreSQL resource lineage, immutable source/materialization triggers,
  idempotency, audit records, jobs, and renewable leases.
- File/S3 CAS behavior and frozen snapshot publication.
- One Alembic head and 128 passing tests with PostgreSQL enabled.

## Architecture test

### Problem being solved

The current repository has individually useful foundation components but lacks a
trustworthy connection from an accepted Analysis request to a scientifically
identified Finding. Several tests pass because they exercise components separately or
run from the source tree. CJ-R00 closes those foundation gaps so later CJs do not
build new product behavior on ambiguous identity, incomplete packaging, or a worker
path that cannot run.

### Current owners and affected boundaries

| Responsibility | Current owner | R00 decision |
| --- | --- | --- |
| Build/package metadata | `pyproject.toml`, Dockerfiles, CI | Extend existing build; no new build system |
| Snapshot identity | `workers/ingest/snapshot.py`, GDC schemas | Version existing snapshot identity; no parallel snapshot service |
| Source/materialization lineage | resource service and PostgreSQL | Reuse unchanged ownership and strengthen validation |
| Analysis lifecycle | `packages/resources/service.py` | Remains the application transaction owner |
| Scientific calculation | `scientific`, `packages/statistics` | Remains deterministic and infrastructure-free |
| Worker execution | `workers/statistics` | Becomes an adapter to the resource-owned execution service |
| Job state | `packages/database/jobs.py` | Add attempt fencing and terminal reaping in the existing queue |
| Finding identity/publication | resource/scientific service plus PostgreSQL | Compute server-side and make immutable |
| GDC access policy | `packages/gdc` | Strengthen denial; do not create another provider layer |

### Data ownership impact

No owner moves. R00 adds versioned identity fields and database constraints to data
already owned by snapshots, analyses, Findings, cohorts, jobs, and attempts. CAS
continues to own bytes; PostgreSQL owns metadata; scientific code owns deterministic
calculation. The worker may request operations but may not directly construct
authoritative Findings or bypass resource transactions.

### Contracts affected

- Snapshot canonical identity advances from implicit v1 to explicit v2.
- Job transitions gain a required attempt token/fencing value.
- Artifact execution gains an internal `AnalysisInputManifest`-compatible contract,
  limited to what is required to run the existing CNV/RNA engine safely.
- Finding publication no longer accepts caller-authoritative IDs or result hashes.
- GDC failures gain a stable terminal `UNAVAILABLE_ACCESS` classification.
- Build/CI contracts gain noninteractive wheel, frontend, image, migration, and
  policy gates.

These are internal/beta contracts. Existing persisted v1 resources remain readable;
new writes use corrected contracts.

### External dependencies

R00 uses the existing GDC REST API, PostgreSQL, S3-compatible storage, Docker,
Next.js, and Python stack. It adds no Jev/TypeSafe SDK, broker, cache, new cloud
provider, or scientific package. Dependency upgrades are allowed only to remove the
verified frontend advisories and must pass compatibility/build/browser tests.

### Simplest viable solution

Extend the existing resource service, queue, snapshot service, and statistics worker.
Do not revive discarded Milestone A/B code wholesale, add a second scheduler, create
a microservice, or implement future Search/Jev/agent resources. One narrow execution
service and one engine registry entry are enough to prove the corrected path.

### Alternatives rejected

- **Put molecular rows back in job JSON:** violates artifact-only execution and
  payload bounds.
- **Rename the queued job to the legacy handler:** preserves the wrong input and
  publication contracts.
- **Let workers write Findings directly:** splits transaction and scientific identity
  ownership.
- **Treat worker ID as fencing:** the same process identity can own multiple attempts
  and cannot distinguish stale completion.
- **Mutate v1 snapshot hashes:** breaks persisted identity; use an explicit version.
- **Delete old records:** unnecessary and destructive; retain readable legacy rows.
- **Implement all of R04 now:** expands R00 beyond readiness; contain unsafe transfer
  now and leave the full planner/slicer to R04.

### Risks and regression surface

- Migration failure or trigger behavior on existing PostgreSQL data.
- Legacy analyses becoming unreadable after stricter schemas.
- Worker crash between CAS publication and metadata commit.
- A stale attempt publishing after reassignment.
- Hash churn from nondeterministic ordering or environment fields.
- False-positive policy scans caused by documentation that describes prohibitions.
- Frontend dependency remediation requiring a breaking Next.js upgrade.
- S3/local differences hidden by unit fakes.

Mitigations are migration round trips, fixture copies of legacy rows, attempt-scoped
temporary output, CAS idempotency, canonical serialization, scan allowlists limited to
policy documentation, and identical File/S3 integration scenarios.

### Architecture confidence

**9/10.** Existing owners and most required primitives are clear and tested. The main
uncertainty is the exact smallest Finding/publication schema that supports current
CNV/RNA execution without pre-implementing R11. A failing end-to-end fixture must be
written before that contract is finalized.

## Target end state

```text
POST /v1/analyses
  -> DurableResourceService validates frozen snapshot/cohort/materializations
  -> compact run_analysis_from_artifacts Job(analysis_id)
  -> fenced statistics-worker attempt
  -> AnalysisExecutionService resolves and verifies immutable artifacts
  -> registered deterministic CNV/RNA engine
  -> server computes scientific/result identity
  -> CAS output publication
  -> one transaction publishes Finding + completes Analysis
  -> fenced job succeeds
```

Every failure has one owner and one terminal/retry classification. No step reads live
GDC, accepts caller molecular matrices, or treats partial evidence as complete.

## File-level change map

| File or area | Planned change |
| --- | --- |
| `pyproject.toml` | Package `scientific`; add only justified test/build tooling and explicit versions |
| `.github/workflows/ci.yml` | Add wheel, PostgreSQL, frontend, migration, image, Compose, and policy jobs |
| `.dockerignore`, `apps/web/.dockerignore` | Exclude Git metadata, caches, local data, secrets, build output, and dependencies |
| `apps/web/package.json` and lockfile | Replace interactive lint; remediate audited dependency path without unreviewed force upgrades |
| `compose.yaml` | Parameterize host ports/project-safe names; add readiness and smoke behavior |
| `packages/schemas/snapshot.py` | Add explicit snapshot identity version/compatibility fields |
| `packages/schemas/resources.py` | Define internal execution/publication responses without caller-owned Finding identity |
| `packages/schemas/finding.py` | Separate computed scientific payload from authoritative identity envelope |
| `workers/ingest/snapshot.py` | Canonical full identity v2 and conflict detection |
| `packages/gdc/mappings/identity.py` | Preserve normalized identity fields and reject contradictory duplicates |
| `packages/gdc/policy.py`, `client.py`, `transfer.py` | Terminal access error and complete-BAM denial/static credential surface |
| `packages/database/models.py`, `jobs.py`, repositories | Attempt token, terminal reaper, immutable Cohort/Finding constraints, publication support |
| `migrations/versions/0005_cj_r00_readiness.py` | Forward/backward-compatible schema and triggers after `0004` |
| `packages/resources/execution.py` (new) | Narrow artifact resolution, engine dispatch, output verification, and transactional publication |
| `packages/resources/service.py` | Server-owned publication and consistent Analysis transitions |
| `packages/statistics/registry.py` (new) | Minimal explicit registry for existing supported engine only |
| `scientific/crossmodal/analysis.py` | Duplicate rejection, finite eligibility, complete result identity inputs |
| `workers/statistics/__main__.py`, dispatcher | Claim artifact job and invoke execution service with fenced context |
| `workers/runtime.py` | Carry attempt token through all transitions and stop stale publication |
| `tests/` | Failing-first unit, contract, scientific, PostgreSQL, worker, packaging, policy, and E2E coverage |
| `scripts/` | Deterministic wheel/Compose/policy verification helpers only where CI shell would be duplicated |

New files are justified only for the execution boundary, engine registry, migration,
build exclusions, and reusable verification scripts. Do not add empty future modules.

## Persistence and compatibility plan

### Migration `0005_cj_r00_readiness`

The implementation must inspect real `0004` schema before finalizing names. Expected
changes are:

1. Add `attempt_token` to current job ownership and attempt records; new claims always
   populate it. Permit null only for readable historical completed attempts if needed.
2. Add explicit snapshot identity version with legacy rows classified as v1.
3. Add immutable update/delete triggers for Cohorts and Findings.
4. Add uniqueness/relationship constraints required for one authoritative Finding
   publication per computed identity or Analysis/result tuple.
5. Add minimal publication metadata only if it cannot live in the canonical Finding
   payload without losing query/integrity guarantees.

Upgrade must preserve every v1 row. Downgrade removes only R00 constraints/columns and
must either preserve compatible data or fail with a documented guard; it must never
silently discard Findings, cohorts, or attempt history.

### Legacy behavior

- Existing v1 snapshots load with `identity_version=1` semantics; no missing metadata
  is invented and they cannot be republished as v2 without reacquisition.
- Existing SHA-only/legacy analyses remain readable but cannot use the new execution
  path unless they possess complete resolvable materialization lineage.
- Existing Findings remain readable and immutable. Their historical identity is not
  relabeled as R00-complete.
- Legacy inline job types are not accepted through new APIs. If retained for reading,
  they are clearly unsupported and not claimed by production workers.

## Detailed implementation sequence

### Phase 0 — Pin the evidence and failing tests

1. Record supported tool versions and the restored baseline in the change record.
2. Add tests that reproduce all eight blockers before implementation:
   disconnected job, missing wheel package, snapshot conflict collapse, duplicate
   molecular overwrite, unchanged result hash after input change, stale attempt
   completion, caller-authored Finding identity, and mutable Cohort/Finding rows.
3. Add negative policy fixtures for auth headers, token-shaped configuration,
   non-open access, authorization response, and complete BAM request.
4. Confirm failures are caused by baseline behavior rather than bad fixtures.

Exit: each blocker has a focused failing test and an identified owner.

### Phase 1 — Reproducible package and build gates

1. Include `scientific` in the wheel and build it in isolation.
2. Install the wheel into a clean environment outside the repository and import API,
   workers, migrations, and the scientific engine.
3. Add noninteractive ESLint configuration/CLI and make typecheck/build/lint distinct.
4. Review the Next/PostCSS advisory and choose the smallest supported upgrade; update
   lockfile with no unrelated dependency churn.
5. Add Docker ignore files, lockfile installs, configurable host bindings, and a
   Compose project smoke command.
6. Expand CI using separate fast/static, PostgreSQL, frontend, and image/Compose jobs.

Exit: source-tree layout can no longer hide an incomplete distribution.

### Phase 2 — Fenced jobs and recovery

1. Add migration/model fields and generate a cryptographically random attempt token
   on every claim/reclaim.
2. Require token plus worker ID in start, heartbeat, succeed, and fail predicates.
3. Pass an immutable execution context to handlers; do not expose a mutable ORM Job
   after the claim transaction closes.
4. Reaper closes expired attempts and terminally fails jobs whose attempt budget is
   exhausted; it requeues only classified retryable work.
5. Separate access-policy, deterministic-data, transient-infrastructure, cancellation,
   and lease-loss outcomes.

Exit: stale attempts cannot change job, Analysis, CAS publication metadata, or Finding
state, and no exhausted job remains active.

### Phase 3 — Complete snapshot identity v2

1. Replace last-write-wins dictionary deduplication with a reusable canonical unique
   function that permits exact duplicates and rejects conflicting records.
2. Hash complete normalized case, sample, aliquot, file, and link records plus all
   selection/source/schema policy versions.
3. Store the identity version in snapshot/provenance records and verify all published
   artifact hashes before registry commit.
4. Add v1 reader fixtures and v2 order-invariance/conflict tests.

Exit: the same v2 digest cannot represent different biological/access selection state.

### Phase 4 — Artifact execution vertical slice

1. Write an end-to-end fixture that registers a frozen snapshot, two compatible
   materializations, and a cohort, then creates an Analysis.
2. Add the narrow registry contract for existing `cnv_rna` only; it declares roles,
   measurement compatibility, complete coverage, parameters, method version, and
   output type.
3. Implement `AnalysisExecutionService`: lock/load Analysis, transition to running,
   construct verified manifest, stage CAS objects, invoke engine, validate outputs,
   compute identities, publish artifacts/Findings, and complete Analysis.
4. Make worker claim `run_analysis_from_artifacts` and pass its fenced execution
   context. The compact payload remains only `analysis_id` plus contract version if
   required.
5. Define failure ordering so a retry can safely detect already published CAS bytes or
   committed Finding and converge without duplication.

Exit: the production API/queue/worker path produces exactly one immutable Finding
from File CAS and S3 CAS fixtures.

### Phase 5 — Scientific and publication correctness

1. Detect duplicate `(case_id, sample_id, gene_id)` keys before map construction.
2. Define finite-value eligibility before the minimum sample check and use the engine’s
   effective `n` for eligible/missing counts.
3. Construct canonical scientific identity including all R00-required fields; sort
   sets by stable biological IDs and reject non-finite JSON.
4. Compute Finding ID and result hash inside the deterministic publication service.
   The API/worker cannot provide authoritative values.
5. Add database immutability and concurrency behavior for Cohorts and Findings.

Exit: input, cohort, parameter, family, environment, or output changes alter identity;
mere input ordering and execution timing do not.

### Phase 6 — Public-data containment

1. Add a typed access failure whose authorization status maps to
   `UNAVAILABLE_ACCESS` and `retryable=false`.
2. Remove/disable any production call that can invoke complete BAM transfer. If the
   current complete-file wrapper remains for bounded non-BAM public files, it requires
   explicit frozen metadata and a maximum-size policy; otherwise quarantine it until
   R04.
3. Add source/config/schema AST scans that distinguish prohibited executable token
   paths from policy documentation describing the prohibition.
4. Prove no environment, API model, CLI option, DB field, worker payload, or log asks
   for GDC credentials.

Exit: no current production action can authenticate to GDC or download a full BAM.

### Phase 7 — Integrated verification and documentation

1. Run migration upgrade/downgrade/upgrade against legacy and fresh PostgreSQL.
2. Run full tests with PostgreSQL and File/S3 stores, worker crash/reclaim, API-to-
   Finding E2E, and corrupt/missing object cases.
3. Build/install wheel outside source tree; run frontend and dependency gates; build
   images; launch two separately named Compose projects with nonconflicting ports.
4. Run policy and secret scans, then inspect logs, DB rows, and object keys for
   credentials or unbounded genomic payloads.
5. Update README, architecture, reproducibility, worker, and roadmap status with only
   verified implemented truth; create a concise R00 change record.

Exit: the machine-verifiable acceptance section passes from a clean checkout.

## Internal delivery order

R00 is one reviewable PR with small, independently understandable commits:

1. failing regression tests and evidence;
2. packaging/frontend/build isolation;
3. migration plus fenced job primitives;
4. snapshot identity v2;
5. artifact execution vertical slice;
6. scientific/Finding identity and immutability;
7. open-data containment;
8. end-to-end verification and current-truth documentation.

Do not merge intermediate commits independently because the schema, worker, and
publication contracts must land together.

## Ownership and implementation

1. **Build/CI:** include `scientific` in the wheel; add wheel/import tests,
   noninteractive frontend lint, pinned reproducible installs, `.dockerignore`,
   configurable Compose ports, and CI gates for Python, PostgreSQL, frontend, images,
   migrations, and policy scans.
2. **Execution:** introduce one artifact-backed execution service under the resource
   boundary. The statistics worker claims `run_analysis_from_artifacts`, loads exact
   registered materializations, verifies contracts, executes a registered engine,
   publishes Findings, and transitions Analysis and Job atomically/idempotently.
   Remove or quarantine legacy inline molecular-row jobs.
3. **Identity:** snapshot v2 hashes complete normalized case/sample/aliquot/file/link
   records and rejects conflicting duplicates. Preserve readable v1 snapshots without
   inventing missing fields.
4. **Scientific identity:** reject duplicate molecular keys; compute eligibility
   after finite-value filtering; bind Finding identity to snapshot, cohort, exact
   inputs, engine/version/parameters, tested family, environment, and output.
   Publication computes IDs/hashes server-side and adds database immutability for
   Cohorts and Findings.
5. **Jobs:** add per-attempt token fencing to start/heartbeat/succeed/fail and a
   reaper that terminally fails exhausted expired work. Ensure one publication.
6. **Acquisition containment:** disable production complete-BAM transfer now. Add a
   deny-by-default acquisition boundary sufficient for R04 to extend; do not build
   the full R04 planner in this gate.
7. **Documentation:** keep current/planned truth explicit and retain this CJ as the
   readiness evidence record.

## Open-data rule

Only GDC records explicitly equal to `access=open` may proceed. R00 adds a static and
runtime denylist for GDC token fields, headers, cookies, token files, dbGaP concepts,
authenticated retries, controlled UUIDs, complete BAM transfer, and unbounded slice
requests. CancerJev service credentials remain unrelated to GDC data access.
Authorization responses
become terminal `UNAVAILABLE_ACCESS`.

## Required tests

- Unit: duplicate identities/rows, finite eligibility, result-identity changes,
  attempt-token fencing, exhausted reaper, permanent access failure.
- Contract: wheel contains all runtime packages; GDC adapter has no credential input;
  unknown/non-open access and complete BAM plans fail before network.
- Scientific: golden results, duplicate rejection, NaN/missingness accounting,
  reordered inputs, changed input hash, parameters, family, and environment.
- Integration: API creates an artifact job; real worker claims it; immutable inputs
  load from File and S3 CAS; exactly one Finding publishes; retries/crashes recover;
  Analysis and Job reach consistent terminal states.
- Migration: upgrade from restored `0004`, downgrade where supported, legacy v1
  snapshot/Finding reads, new immutability/fencing constraints.
- Frontend/build: noninteractive lint, typecheck, production build, dependency audit
  policy, isolated wheel import, image build, Compose with configurable ports.
- Negative security: auth-header/token schema scan, alternate hosts, controlled or
  unknown access, path/symlink escape, corrupt CAS, oversized payloads, full BAM.

## Machine-verifiable acceptance

- Clean checkout on Python 3.12 installs a wheel and imports every worker plus
  `scientific` outside the repository root.
- Ruff, complete PostgreSQL pytest suite, frontend lint/typecheck/build, dependency
  policy, Alembic single-head/round-trip, image build, and isolated Compose smoke pass.
- A real `POST /v1/analyses` fixture reaches one immutable Finding through the
  production worker; no inline matrices appear in the job payload.
- Killing and replacing a worker cannot allow the stale attempt to publish.
- Conflicting frozen metadata and duplicate molecular keys fail deterministically.
- Changing any scientific identity field changes the Finding identity.
- Static and dynamic scans find no usable GDC credential or complete-BAM path.
- Documentation contains no implemented claim unsupported by the verified system.

## Test matrix and planned locations

| Test area | Planned file | Required scenarios |
| --- | --- | --- |
| Packaging | `tests/contract/test_distribution.py` | Wheel content, isolated imports, no source-tree fallback |
| Policy surface | `tests/contract/test_open_data_surface.py` | Config/schema/env/CLI/header/token/full-BAM denial |
| Snapshot v2 | `tests/unit/test_snapshot_service.py` | Full identity, conflicts, ordering, v1 read, v2 hash changes |
| Scientific identity | `tests/scientific/test_crossmodal_golden.py` | Duplicates, finite eligibility, hash inclusion/exclusion matrix |
| Job fencing | `tests/unit/test_queue.py` plus PostgreSQL integration | Attempt token, stale completion, exhaustion, reaper, cancellation |
| Artifact execution | `tests/integration/test_analysis_execution.py` | API-to-worker-to-Finding, File/S3 parity, replay, crash windows |
| Persistence | `tests/integration/test_durable_resources.py` | Cohort/Finding immutability, caller identity rejection, legacy reads |
| Migration | `tests/integration/test_migration_0005.py` | Fresh/legacy upgrade, downgrade guard, data/trigger preservation |
| Frontend | web lint/typecheck/build and focused browser smoke | Noninteractive gates, API failure display, no token UI |
| Compose | `scripts/compose_smoke.py` | Parameterized ports, migrations, health, workers, shared CAS |

Test names may be adjusted to repository convention, but scenarios cannot be omitted
or hidden inside one opaque end-to-end assertion.

## Acceptance command set

The implementation PR must publish the exact tool versions and results for commands
equivalent to:

```bash
python -m ruff check .
python -m pytest -q
python -m alembic heads
python -m build
# install the wheel into an isolated environment outside the checkout

cd apps/web
npm ci
npm run lint
npm run typecheck
npm run build
npm audit --omit=dev

docker compose config --quiet
docker compose --project-name cancerjev-r00-a up --build -d
python scripts/compose_smoke.py --project cancerjev-r00-a
docker compose --project-name cancerjev-r00-b up --build -d
```

The final test must use disposable PostgreSQL and object storage. Cleanup commands and
failure logs are recorded, but credentials and genomic payloads are redacted. If npm
audit policy allows a documented temporary exception, it must identify the advisory,
reachability, compensating control, owner, and expiration; an unbounded waiver fails
R00.

## Observability and failure semantics

Add structured events/metrics for job claim/start/heartbeat/reclaim/terminal state,
Analysis transitions, manifest resolution, engine start/end, Finding publication,
snapshot identity conflict, CAS integrity failure, and open-data denial. Records use
stable resource/attempt IDs and bounded reason codes. They exclude molecular rows,
provider bodies, credentials, cookies, and filesystem secrets.

Minimum terminal reason families:

- `UNAVAILABLE_ACCESS` — permanent public-access boundary;
- `INVALID_SCIENTIFIC_INPUT` — permanent identity/schema/coverage/duplicate failure;
- `INTEGRITY_FAILURE` — permanent until bytes/registry are repaired;
- `UNSUPPORTED_ENGINE_OR_VERSION` — permanent contract mismatch;
- `TRANSIENT_INFRASTRUCTURE` — budgeted retry permitted;
- `LEASE_LOST` — stale attempt stops without publication;
- `CANCELLED` — explicit terminal cancellation;
- `RETRY_EXHAUSTED` — terminal after the allowed attempt budget.

## Security review checklist

- GDC client construction cannot receive caller headers or alternate hosts.
- No redirect follows outside the official origin.
- Error messages/logs do not echo secrets, signed object URLs, or raw source content.
- Staged paths are attempt-local, contained, and resistant to traversal/symlink swaps.
- CAS reuse verifies size/hash; permission/service failures are not treated as missing.
- Job, Analysis, Finding, and object references cannot cross a future project boundary;
  R00 documents the API as local-only until R06 rather than inventing partial auth.
- Subprocesses use argument arrays, fixed executable resolution, timeouts, and bounded
  output; no shell interpolation is introduced.
- CI policy scanning tests its own positive and negative fixtures to prevent silent
  bypass or permanent false positives.

## Rollout and rollback

1. Deploy migration before new worker/API code; old processes must tolerate additive
   fields during the rolling window or deployment must use a documented stop-the-world
   local/beta upgrade.
2. Start one R00 worker with new job claim enabled and verify a synthetic fixture.
3. Enable API creation only after the worker readiness probe advertises the matching
   execution contract version.
4. Monitor stuck jobs, lease loss, duplicate-publication conflicts, CAS integrity, and
   Analysis/Job terminal-state mismatch.
5. Roll back application code only while schema compatibility is proven. Do not
   downgrade destructively after new immutable resources exist; forward-fix or use the
   guarded downgrade procedure.

R00 does not require production rollout, but its migration and worker contracts must
be safe enough for R33 to operationalize later.

## Reviewer checklist

- [ ] Every audit blocker has a failing-before/passing-after test.
- [ ] No discarded branch implementation was copied without line-by-line review.
- [ ] Exactly one module owns Analysis/Finding publication.
- [ ] Worker and API cannot supply authoritative scientific identity fields.
- [ ] Attempt token participates in every mutating job transition.
- [ ] Snapshot v2 includes complete normalized biological/access state.
- [ ] Legacy resources remain readable and are not falsely upgraded.
- [ ] No complete BAM or GDC credential route exists.
- [ ] Wheel, frontend, database, File/S3, image, and Compose gates actually ran.
- [ ] Full diff contains no unrelated refactor, dependency, generated output, or secret.
- [ ] README/architecture describe only verified post-R00 behavior.

## Non-goals

Runtime isolation and quotas (R06), the complete acquisition planner/slicer (R04), new
discovery engines (R08–R12), Jev (R13), research agents (R20), UI expansion (R26),
and production deployment (R33).

## Definition of done

All acceptance commands and negative probes are recorded with versions and outputs;
the full diff is reviewed; no discarded branch code is copied wholesale; current
architecture and roadmap status are updated; CJ-R01 can begin without inheriting a
known foundation blocker.
