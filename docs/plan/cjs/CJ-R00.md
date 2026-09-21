# CJ-R00 — Restored-main readiness gate

**Status:** required before CJ-R01

**Baseline:** `2bf6c68d93741b9974f46983e0a35c691d69c1f1`

**Classification:** large cross-cutting correctness repair

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
- The API has no application identity or authorization and must remain explicitly
  local-development-only until CJ-R06.
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
requests. CancerJev login remains unrelated to GDC access. Authorization responses
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

## Non-goals

Application accounts (R06), the complete acquisition planner/slicer (R04), new
discovery engines (R08–R12), Jev (R13), research agents (R20), UI expansion (R26),
and production deployment (R33).

## Definition of done

All acceptance commands and negative probes are recorded with versions and outputs;
the full diff is reviewed; no discarded branch code is copied wholesale; current
architecture and roadmap status are updated; CJ-R01 can begin without inheriting a
known foundation blocker.
