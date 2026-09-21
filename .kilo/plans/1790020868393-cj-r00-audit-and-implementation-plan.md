# CJ-R00 Audit and Implementation Plan

Audit date: 2026-09-22. Tree: branch `codex/cj-r00-implementation-plan`, HEAD `5cd1d47` (one docs-only commit after baseline `2bf6c68`), with an uncommitted expansion of `docs/plan/cjs/CJ-R00.md` in the working tree. No code differs from the baseline. Every CJ-R00 claim below was re-verified directly against source.

**AGENTS.md alignment (2026-09-22):** `AGENTS.md` now exists at the repo root and governs all CJ work. CJ-R00 was re-analyzed rule-by-rule against it: compliant on authority boundaries, dependency direction, state distinctions, open-data rules, KISS, testing depth, PostgreSQL invariants, fencing, immutable inputs, duplicate rejection, eligibility, canonical identity, record immutability, and migration completeness. Corrected items: R06 references (login/accounts → runtime isolation/quotas; no end-user login per AGENTS.md §6), and the roadmap now records R28–R32 as an optional program that never blocks native production (R33 native deps: R01–R27). These corrections changed no implementation units in this plan.

---

## A. EXECUTIVE SUMMARY

- **CJ-R00 is not implemented.** All 8 blockers reproduce in the current tree. No remediation exists on main or in the working tree.
- **Main is NOT safe to begin CJ-R01.** The artifact-backed analysis path is disconnected end-to-end: `POST /v1/analyses` queues a job type no worker claims, so every durable Analysis is permanently `queued`.
- **Highest-risk blockers:** (1) disconnected worker path; (7) caller-authored Finding identity; (5) missing job fencing + permanently nonterminal exhausted jobs; (2) wheel omits `scientific` (masked by Docker/editable layouts).
- **Architectural condition: good bones, broken connections.** Ownership boundaries (gdc/storage/resources/database/statistics/worker) are clean and well-tested in isolation. The GDC policy layer, CAS, materialization lineage, and immutability triggers are strengths to preserve. The failures are all at the seams the existing tests don't cross: worker↔queue, wheel↔install, snapshot identity↔full records, eligibility↔statistic, publication↔identity, build↔CI.

---

## B. VERIFIED CJ-R00 FINDINGS

### Blocker 1 — Durable analyses cannot execute
- **Status:** CONFIRMED — **Severity: critical (the R00 headline defect)**
- **Files:** `packages/resources/service.py:349-358`, `workers/statistics/__main__.py:11-14`, `workers/statistics/analysis.py:5-16`
- **Current behavior:** `create_analysis()` saves `Job(job_type="run_analysis_from_artifacts", payload={"analysis_id": ...})`. The statistics worker claims only `("run_analysis", "reproduce_finding")`. Grep confirms no production code ever enqueues those two legacy types (`enqueue()` in `packages/database/jobs.py:18` is dead code); the legacy handler expects inline `cnv_rows`/`rna_rows` payloads nothing produces. Analyses sit in `queued` forever; no Finding, no terminal Analysis state.
- **Why it violates CJ-R00:** the target end state (API → fenced worker → deterministic engine → one immutable Finding) is impossible.
- **Smallest fix:** claim `run_analysis_from_artifacts` in the statistics worker and dispatch to a new application-owned execution service; delete the dead inline handler (`workers/statistics/analysis.py`) and stop claiming legacy types.

### Blocker 2 — Wheel omits `scientific`
- **Status:** CONFIRMED — **Severity: critical (reproducibility/packaging)**
- **Files:** `pyproject.toml:38-39`, `Dockerfile:4-10`, `.github/workflows/ci.yml:36`
- **Current behavior:** `[tool.hatch.build.targets.wheel] packages = ["apps", "packages", "workers"]`. The Dockerfile copies `scientific/` into `/app` (importable via CWD, masking the omission); CI installs `-e` (also masking). An installed wheel outside the source tree cannot import `scientific.crossmodal`.
- **Smallest fix:** add `"scientific"` to wheel packages; add an isolated build+install+import contract test and CI job.

### Blocker 3 — Snapshot identity collapses conflicting biological records
- **Status:** CONFIRMED — **Severity: high**
- **Files:** `workers/ingest/snapshot.py:46-54` (`unique()` last-write-wins dict comprehension for cases/samples/aliquots), `workers/ingest/snapshot.py:65-85` (identity dict stores only `case_ids`/`sample_ids`/`aliquot_ids` lists, not full normalized records; full records exist only for `objects` and `file_identity_links`)
- **Current behavior:** two hits carrying the same `case_id` with different `submitter_id`/`project_id` (or sample/aliquot equivalents) are silently collapsed to whichever sorts last into the dict; the digest cannot distinguish them. The collapsed records also flow into the published `cases/samples/aliquots.parquet` artifacts.
- **Smallest fix:** a reusable `unique_records()` that permits exact duplicates and raises on conflicting records; hash full normalized case/sample/aliquot records; explicit `identity_version=2`.

### Blocker 4 — CNV/RNA duplicate collapse + incomplete result identity
- **Status:** CONFIRMED — **Severity: high**
- **Files:** `scientific/crossmodal/analysis.py:16-17` (dict comprehensions keyed `(case_id, sample_id, gene_id)`, last-write-wins), `scientific/crossmodal/analysis.py:32-41` (identity dict = snapshot_id, gene, effect, p, q, cases, analysis label only)
- **Current behavior:** duplicate biological rows silently overwrite; `result_hash` excludes declared input hashes (they are accepted and stored on the Finding but never hashed), cohort identity, parameters, engine version, eligibility policy, environment, and canonical outputs.
- **Smallest fix:** reject duplicate keys before map construction; build complete identity per Section H.

### Blocker 5 — No attempt fencing; exhausted expired jobs never terminal
- **Status:** CONFIRMED — **Severity: high**
- **Files:** `packages/database/jobs.py:25-56` (claim), `:87-96` (`_owned` predicates on `job_id`+`worker_id` only), `:77-84` (`fail` only from `running`), `packages/database/models.py:229-265` (Job/JobAttempt have no token column), `workers/runtime.py:34-44` (heartbeat checks only worker_id)
- **Current behavior:**
  - No per-attempt token anywhere. A stale heartbeat thread from worker A (which can outlive `LeaseHeartbeat.stop()`'s bounded join) renews the lease of a *newer* attempt re-claimed under the same `worker_id` — the concrete stale-publication vector CJ-R00 describes.
  - Claim selection requires `attempt_count < max_attempts`, so a job in `claimed`/`running` with an expired lease and exhausted budget is selected by nothing; no reaper exists. It is permanently nonterminal (verified: no other writer of terminal states).
- **Smallest fix:** `attempt_token` on jobs+attempts generated at claim; require token in start/heartbeat/succeed/fail; add `reap_expired()` that terminally fails exhausted expired jobs and closes dangling attempts; allow `fail` from `claimed`.

### Blocker 6 — Transfer wrapper performs unrestricted complete-file download; no terminal access classification
- **Status:** CONFIRMED — **Severity: high (policy)**
- **Files:** `packages/gdc/transfer.py:42-56` (`download()` invokes `gdc-client download` on any manifest; no data-type gate, no size bound, `subprocess.run` without `timeout`), `packages/gdc/client.py:156-161` (401/403 raise generic `GDCError`, no typed `UNAVAILABLE_ACCESS`)
- **Current behavior:** no production caller invokes `GDCTransfer.download` today (tests only — grep verified), but the unsafe acquisition surface exists uncontained. Authorization responses are not a stable terminal class.
- **Smallest fix (containment only, not the R04 planner):** typed `UnavailableAccess` error (401/403 → reason `UNAVAILABLE_ACCESS`, `retryable=false`); `download()` requires frozen `SnapshotObject` metadata with `access=open`, rejects BAM `data_format`/`data_type`, enforces a max-size policy, and gets a subprocess timeout; static policy scan with self-testing fixtures.

### Blocker 7 — `persist_finding()` accepts caller-authored identity
- **Status:** CONFIRMED — **Severity: critical**
- **Files:** `packages/resources/service.py:401-414`, `packages/schemas/resources.py:135-144` (`FindingCreate` carries caller `finding_id`, `result_hash`, `analysis_version`, `payload`)
- **Current behavior:** the only check is `analysis.state == "completed"`; the Finding row is `Finding(**request.model_dump())`. No recomputation or attestation. (No HTTP endpoint exposes it today — the defect is at the service boundary the worker would use.)
- **Smallest fix:** remove `FindingCreate` from the service surface; publication becomes internal-only, invoked by the execution service with server-computed identity; keep read APIs unchanged.

### Blocker 8 — Cohorts and Findings have no DB immutability
- **Status:** CONFIRMED — **Severity: high**
- **Files:** `migrations/versions/0002_durable_resources.py:107-126`, `0003_gdc_materialization.py:40-43`, `0004_analysis_materialization_inputs.py:13-33`
- **Current behavior:** triggers protect `dataset_objects`, `audit_events`, published `dataset_snapshots`, `snapshot_artifacts`, `materialization_sources`, `materializations`, and Analysis scientific inputs. **Not protected:** `cohorts`, `findings` (also `cases`/`samples`/`aliquots`/`snapshot_files` — not required by CJ-R00). `findings.result_hash` is nullable with no uniqueness constraint; `finding_id` derives from only 12 hex chars (48 bits).
- **Smallest fix:** migration `0005` adds `cancerjev_reject_immutable_mutation()` triggers for cohorts and findings, plus `unique(analysis_id, result_hash)` and a longer deterministic `finding_id`.

### Quality/operational risks
- **Interactive lint:** CONFIRMED — `apps/web/package.json` `"lint": "next lint"` (interactive under Next 15; README verification baseline records the failure).
- **npm audit (1 high, 1 moderate, Next/PostCSS path):** DOCUMENTED, NOT RE-VERIFIED here (tool-run restrictions); treat as PARTIAL — must be reproduced and remediated during implementation.
- **No `.dockerignore` (root or web):** CONFIRMED (glob). Also `apps/web/Dockerfile:4` uses `npm install` instead of `npm ci` (non-reproducible image builds).
- **Compose hard-coded host ports:** CONFIRMED — `compose.yaml:16` (8000), `:71` (3000), `:102-103` (9000/9001). Postgres correctly has no host mapping.
- **CI blind:** CONFIRMED — `.github/workflows/ci.yml` is a single Python job (editable install, ruff, pytest w/ PostgreSQL). No wheel, frontend, image, Compose, migration round-trip, policy/secret scans, or Python-version gate beyond 3.12 implicit.
- **API has no application authorization boundary:** CONFIRMED (by design; no end-user login exists per AGENTS.md §6 — API stays local-development-only until CJ-R06 runtime isolation) — README/ARCHITECTURE already document local-only truth; no change needed beyond keeping it truthful.

---

## C. ADDITIONAL FINDINGS (not explicit in CJ-R00)

1. **Eligibility/missingness mismatch (scientific correctness):** `analyze_cnv_rna` (scientific/crossmodal/analysis.py:30-31, 49-57) computes `eligible_cases`/`missing_n` from *all* paired rows, while `cnv_expression` (packages/statistics/crossmodal.py:17-18) filters non-finite values internally. `CNVRecord.cnv_value` is nullable (`None` → NaN). Reported population ≠ population used by the statistic; the engine's effective `n` is discarded.
2. **Single bad gene aborts the whole analysis:** genes with ≥4 pairs but <4 *finite* pairs, or zero variance, raise `ValueError` from `cnv_expression` — unhandled, so one untestable gene fails the entire Analysis instead of being skipped as not-tested.
3. **No cohort filtering:** the engine path never restricts rows to cohort membership; `cohort_size` is caller-supplied in the dead legacy payload. Missingness has no defined denominator once the artifact path connects.
4. **Job failure never fails the Analysis:** nothing couples terminal job failure to `Analysis.state`; once the worker connects, retry exhaustion leaves Analysis `running`/`queued` forever. `transition_analysis` and `ANALYSIS_TRANSITIONS` exist but no owner for failure.
5. **`fail()` unreachable before `start()`:** `packages/database/jobs.py:78` allows failing only from `running`; a crash between claim and start cannot record the failure (job waits out lease expiry). Allow `fail` from `claimed`.
6. **`enqueue()` is dead code** and the legacy `run_analysis`/`reproduce_finding` handlers reference payload keys no producer creates — pure dead path to remove.
7. **`scripts/compose_smoke.py:96` hard-codes alembic version `0004`** — will break the moment migration `0005` lands; must be updated in the same unit.
8. **Finding publication is not concurrency-safe:** no unique constraint on `(analysis_id, result_hash)`; `finding_id` suffix is 48 bits; concurrent attempts could insert duplicate authoritative findings.
9. **`create_analysis` never uses the `requested` state** (inserts directly as `queued`); harmless dead transition — leave the state machine as-is.
10. **`_reject_matrix_payload` is size/keyword-based only** (`packages/resources/service.py:440-445`): a small matrix under an unlisted key passes. Acceptable for R00 — the real fix is artifact-only execution, which R00 delivers.
11. **No failure-reason taxonomy on jobs** — only a boolean `retryable` via exception attribute (`workers/runtime.py:86`); CJ-R00 observability requires bounded reason codes.
12. **Test-suite blind spots:** `tests/unit/test_queue.py` uses `FakeSession` (no SQL), so fencing/exhaustion must gain real PostgreSQL integration coverage; no test imports the installed wheel; no test crosses API→worker→Finding.

---

## D. VERIFIED STRENGTHS TO PRESERVE (do not rewrite)

- **GDC client policy** (`packages/gdc/client.py`): official-host enforcement, `trust_env=False`, auth-header/redirect rejection, response byte limits, open-only pagination filters, retry classification, manifest validation against frozen identity (`packages/gdc/manifest.py`).
- **`packages/gdc/policy.py`**: `official_api`, `require_open` fail-closed semantics.
- **Canonical parsers + materialization** (`packages/gdc/parsers.py`, `materialization.py`): verified input bytes, private staged copy, bounded batches, logical hashing, zstd parquet, diagnostics JSONL.
- **CAS** (`packages/storage/objects.py`): File (hardlink publish) + S3 stores, hash-on-stage verification, permission-vs-missing distinction; `FrozenSnapshotReader.stage` path containment.
- **Frozen snapshot publication** (`packages/storage/snapshots.py`): atomic rename, COMPLETE.json hash manifest, conflict verification.
- **Durable resource layer**: snapshot/source/materialization immutability triggers, Analysis input freeze trigger, idempotency records, audit events, compact job payloads, `SKIP LOCKED` claim, cohort membership validation against frozen graph, clinical-pages acquisition with frozen-UUID provenance.
- **Deterministic primitives**: `benjamini_hochberg`, `cnv_expression`/`mutation_expression`, `FrozenIdentityResolver`.

---

## E. CURRENT EXECUTION FLOW (POST /v1/analyses)

```text
POST /v1/analyses (apps/api/main.py:235-242, Idempotency-Key header)
  -> db.begin(): DurableResourceService.create_analysis (service.py:305-379)
     validates snapshot+cohort pairing, cohort membership vs frozen graph,
     resolves input materializations, verifies expected hashes,
     idempotency.reserve(analysis.create)
     -> Job(job_type="run_analysis_from_artifacts", payload={analysis_id}, state=queued)
     -> Analysis(state=queued, engine, parameters, expected_input_artifacts, lineage)
     -> audit events; COMMIT
  -> 201 AnalysisResponse
     |
     X-> BREAK: workers/statistics/__main__.py claims only ("run_analysis",
        "reproduce_finding"). No producer enqueues those types; enqueue() unused.
        The queued job is never claimed; Analysis never leaves "queued";
        transition_analysis/persist_finding have no production caller;
        no Finding exists; no terminal state. (Legacy handler expects inline
        cnv_rows/rna_rows — a payload contract CJ-R00 forbids reviving.)
```

Verified break points: claim-type mismatch (worker `__main__.py:12`), absent failure coupling (runtime has no Analysis hook), absent publication owner (`persist_finding` only reachable from tests with caller identity).

---

## F. PROPOSED R00 ARCHITECTURE (smallest correct)

One new application service, one minimal registry, fenced existing queue. **No new infrastructure.**

```text
POST /v1/analyses  (unchanged contract)
  -> DurableResourceService.create_analysis        [unchanged; still tx owner]
  -> Job(run_analysis_from_artifacts, {analysis_id})
  -> workers/runtime.run_worker                    [adapter only]
       claim (SKIP LOCKED) + attempt_token  -> immutable ClaimedJob ctx
       reap_expired() on each poll
       start/heartbeat(fenced)
       handler = packages/resources/execution.py: AnalysisExecutionService.run(claimed)
  -> AnalysisExecutionService (packages/resources/execution.py — the deterministic
     execution owner; workers may not construct Findings):
       1. resolve+lock Analysis; verify job fence in-tx; queued->running
          (idempotent: running already + existing Finding => converge)
       2. resolve cohort, snapshot, materializations; verify expected_input_artifacts
          exactly match registered output hashes (else INVALID_SCIENTIFIC_INPUT)
       3. stage materialization outputs from File/S3 CAS into attempt-local temp dir
          (CAS stage verifies sha256; mismatch => INTEGRITY_FAILURE)
       4. read projected columns from canonical parquet (bounded batches)
       5. registry lookup (packages/statistics/registry.py): cnv_rna contract
          (required modalities/measurements, parameters, method_version,
          output finding_type); mismatch => UNSUPPORTED_ENGINE_OR_VERSION
       6. scientific package: analyze_cnv_rna(ctx, cnv_rows, rna_rows)
          - rejects duplicate (case_id, sample_id, gene_id) keys
          - finite-eligibility before min-pairs check; effective n drives
            eligible/missing; cohort-filtered rows; untestable genes skipped
          - computes Finding payload + complete result identity (Section H)
       7. publish: one transaction — verify fence; Finding inserts (server-computed
          finding_id/result_hash; converge on unique(analysis_id, result_hash));
          Analysis -> completed; audit
       8. return result summary -> run_worker succeed(fenced: job+worker+token)
  -> on failure: typed ExecutionFailure(reason, retryable)
       deterministic reasons => fail(non-retryable) + Analysis -> failed
       transient => fail(retryable) => requeue
       lease lost => LEASE_LOST; no publication
       terminal job failure hook => Analysis -> failed (consistent terminal states)
```

Failure-ordering for idempotent replay: CAS outputs (if any) are content-addressed (idempotent); Finding insert converges via unique key; Analysis completed + job still claimed => next attempt converges and succeeds.

**Removed/quarantined:** legacy `run_analysis`/`reproduce_finding` claim types and `workers/statistics/analysis.py` inline handler (dead code, wrong contract); `FindingCreate` caller-identity path; `enqueue()` dead helper.

---

## G. DATABASE / MIGRATION PLAN — `migrations/versions/0005_cj_r00_readiness.py`

After `0004`, additive only; verified against real 0004 schema:

1. `ALTER TABLE jobs ADD COLUMN attempt_token varchar(64);` (nullable; every claim sets it; legacy in-flight jobs simply lose their claim to lease expiry)
2. `ALTER TABLE job_attempts ADD COLUMN attempt_token varchar(64);`
3. `ALTER TABLE jobs ADD COLUMN failure_reason varchar(50);`
4. `ALTER TABLE dataset_snapshots ADD COLUMN identity_version integer NOT NULL DEFAULT 1;` (existing rows are v1; never backfilled/invented)
5. `CREATE TRIGGER trg_cohorts_immutable BEFORE UPDATE OR DELETE ON cohorts ... cancerjev_reject_immutable_mutation();`
6. `CREATE TRIGGER trg_findings_immutable BEFORE UPDATE OR DELETE ON findings ... cancerjev_reject_immutable_mutation();`
7. `CREATE UNIQUE INDEX uq_findings_analysis_result ON findings(analysis_id, result_hash) WHERE result_hash IS NOT NULL;` — documented guard: migration fails loudly if legacy duplicates exist (none can exist today: `persist_finding` has no production caller); never silently discards.
8. `Index("ix_jobs_expired", ...)` if the reaper query needs it (measure first; claim index `ix_jobs_claim` likely suffices).

**Order:** migration ships in the same PR before worker/API code (rolling-window safe: all columns additive; old code ignores them).
**Downgrade:** drop triggers, unique index, new columns. Preserves all rows; never deletes Findings/cohorts/attempts. Update `scripts/compose_smoke.py` expected head to `0005`.
**Models:** mirror in `packages/database/models.py` (`Job.attempt_token`, `Job.failure_reason`, `JobAttempt.attempt_token`, `DatasetSnapshot.identity_version`).
**Tests:** fresh upgrade `0001→head`; upgrade from populated `0004` fixture rows; `downgrade 0005→0004→head` round-trip preserving v1 snapshots, legacy Findings, attempt history; immutability triggers fire on UPDATE/DELETE of cohorts/findings; unique index rejects duplicate publication.

---

## H. SCIENTIFIC IDENTITY PLAN (Finding/result identity)

Computed **server-side only** (scientific package pure function; execution service publishes; API/worker cannot supply values).

**Identity-bearing (enter `result_hash`):**
- `identity_contract_version: "cj-r00-result-v1"`
- snapshot: `snapshot_id` + `snapshot_hash`
- cohort: `content_hash`
- exact immutable inputs: sorted list of materialization `output_sha256` (exact artifact bytes)
- engine: name, engine_version, method_version (registry)
- parameters: canonicalized analysis parameters
- tested family/universe: `finding_type`, `gene_id`
- eligibility policy: `{min_pairs, finite_required: true, eligibility_version}`
- environment/runtime: `{python, numpy, scipy}` versions
- canonical output digest (hash of: effect_size, p_value, q_value, confidence_interval, n_effective, eligible_case_ids, eligible_sample_ids, missing_n, qc_flags)

**Derived:** `finding_id = "F-" + canonical_hash({analysis_id, result_hash})[:32]` (per-Analysis uniqueness; 128-bit suffix).
**DB constraint:** `unique(analysis_id, result_hash)`; `save()` converges on conflict.

**Informational only (payload, excluded from identity):** row counts, materialization metadata (already bound via artifact hashes), timestamps.
**Explicitly excluded:** wall-clock timing, worker/job/attempt identity, execution attempt count, Jev/agent output (n/a in R00), UI state, input row *ordering* (canonical sorting everywhere).

**Order-invariance requirement:** reordering input rows, cases, or samples must not change identity (all sets/lists sorted by stable biological IDs before hashing; non-finite values rejected before JSON canonicalization).

---

## I. SNAPSHOT IDENTITY V2 PLAN

1. **Reusable conflict-aware unique:** `unique_records(records, key_attr)` in `packages/schemas/identity.py` — exact duplicates collapse; same key with differing canonical dump raises `ValueError("conflicting_<type>_identity")`. Replaces the last-write-wins comprehension in `workers/ingest/snapshot.py:46-54` (cases by `case_id`, samples by `sample_id`, aliquots by `aliquot_id`).
2. **Full-record hashing:** v2 identity dict replaces `case_ids/sample_ids/aliquot_ids` lists with full normalized record dumps (`cases`, `samples`, `aliquots`), keeping existing full `objects` and `file_identity_links`, plus all existing policy/schema/selection version fields, plus `"identity_version": 2`. Same v2 digest can never represent different biological/access state.
3. **Version plumbing:** `SnapshotRecord.identity_version: int = 1` (v1 JSON still deserializes — additive field with default); new snapshots publish `identity_version=2`; `register_snapshot` persists it to `dataset_snapshots.identity_version`.
4. **v1 compatibility:** existing v1 snapshots and their `cases/samples/aliquots.parquet` artifacts remain readable by `FrozenSnapshotReader` unchanged; no invented metadata; v1 rows cannot be "upgraded" to v2 without reacquisition (identity_version is part of the published record).
5. **Artifact consistency:** parquet artifacts are written from the deduplicated conflict-checked records (already the case; now guaranteed conflict-free); `_snapshot_artifacts` role mapping unchanged.

**Tests:** conflicting duplicate case/sample/aliquot raises; exact duplicates collapse; order invariance (input hit order permuted → same digest); v1 fixture loads with `identity_version=1`; any field change (sample_type, submitter_id, link set) changes the v2 digest.

---

## J. JOB FENCING PLAN

Lifecycle: **claim → token generated → start → heartbeat → execute → publish → succeed/fail**

1. `claim()` generates `attempt_token = secrets.token_hex(32)`, writes it to `jobs.attempt_token` and the new `JobAttempt`, and returns an immutable `ClaimedJob` dataclass (`job_id`, `job_type`, `payload`, `worker_id`, `attempt_token`). No live ORM `Job` crosses the claim transaction.
2. `start`, `heartbeat`, `succeed`, `fail` each take `(session, job_id, worker_id, attempt_token)` and predicate on **all three** plus lease validity (`_owned` upgrade). A stale heartbeat thread from a prior attempt fails token check → `LeaseLostError` → stops renewing.
3. The execution service calls `verify_lease(session, job_id, worker_id, attempt_token)` **inside** its running-transition and publication transactions, so a stale attempt cannot change Analysis state, CAS publication metadata, or Finding rows even between heartbeats.
4. **Reaper `reap_expired(session)`:** run each worker poll. For jobs in `claimed`/`running` with expired lease: close dangling attempt records; if `attempt_count >= max_attempts` → terminal `failed` with `failure_reason="RETRY_EXHAUSTED"` (and completed_at); otherwise leave to normal claim-based reclaim (attempt record already closed with "lease expired").
5. `fail()` accepts state `claimed` or `running`; records `failure_reason` (bounded enum: `UNAVAILABLE_ACCESS`, `INVALID_SCIENTIFIC_INPUT`, `INTEGRITY_FAILURE`, `UNSUPPORTED_ENGINE_OR_VERSION`, `TRANSIENT_INFRASTRUCTURE`, `RETRY_EXHAUSTED`; `LEASE_LOST` never mutates job state).
6. **Stale worker behavior:** any fenced mutation after reclaim raises `LeaseLostError`; runtime logs and drops the result without publication; deterministic publication convergence makes double-execution harmless.
7. `workers/runtime.py`: passes `ClaimedJob` to handlers (ingest handler adapted); optional per-job-type `on_terminal_failure` hook (fresh session) so the statistics worker can mark its Analysis failed when a job reaches terminal failure — keeping runtime generic and scientific ownership in the service.

**Tests (unit + PostgreSQL integration):** stale succeed/fail rejected after reclaim by another worker; stale heartbeat cannot renew newer attempt (same worker_id); exhausted+expired job becomes `failed`/`RETRY_EXHAUSTED` via reaper; claim-from-`claimed`-expired still works below budget; crash between claim and start recordable.

---

## K. ACQUISITION CONTAINMENT PLAN (R04 planner explicitly deferred)

- **Disabled/denied immediately:** `GDCTransfer.download` without frozen metadata; any BAM source (`data_format == "BAM"` or `data_type` containing "BAM") → `ValueError` before subprocess; source not `access=open` → fail closed; file_size above a fixed max-transfer policy → rejected; subprocess gets an explicit `timeout`.
- **Typed access failure:** `packages/gdc/client.py` maps HTTP 401/403 → `GDCUnavailableAccess(GDCError)` with `retryable=False` and `reason="UNAVAILABLE_ACCESS"`; no credential seeking, no authenticated retry (terminal).
- **Still allowed:** bounded official metadata (`/status`, `/projects`, `/cases`, `/files` pagination with open filter and byte limits), frozen clinical pages acquisition, local `register_local_source` with verified md5/size, manifest generation/validation.
- **Static policy scan:** `scripts/policy_scan.py` scans `packages/`, `workers/`, `apps/`, `migrations/`, `scripts/` for executable surfaces of: `X-Auth-Token`/`authorization`/`cookie` on GDC requests, GDC token config/env/CLI fields, token files, dbGaP concepts, complete-BAM invocation. Documentation/tests describing prohibitions are allowlisted by path. The scanner tests itself with positive+negative fixtures (`tests/contract/test_open_data_surface.py`) to prevent bypass and false positives.
- **Deferred to CJ-R04:** AcquisitionPlan/Receipt, BAM slicing, minimal-transfer planner, any new acquisition job types. R00 only proves no current production action can authenticate to GDC or download a full BAM.

---

## L. BUILD / CI PLAN

**Python (static):** ruff check (3.12 target, unchanged config); `python -m alembic heads` single-head check.
**Python (PostgreSQL):** full pytest against a postgres:16 service (existing job, keep).
**Migrations:** dedicated job: fresh `upgrade head`; `downgrade 0003` → `upgrade head` round-trip; populated-0004-fixture upgrade; assert head `0005`.
**Wheel:** `python -m build` (add `build` to dev extras with pinned range); install wheel into a venv **outside the checkout**; import `apps.api.main`, every worker module, `scientific.crossmodal`, `packages.statistics.registry`; assert `scientific/` present in wheel RECORD; assert no source-tree fallback (run from a different CWD).
**Frontend (Node 22):** `npm ci`; `npm run lint` via direct ESLint CLI + `eslint.config.mjs` (FlatCompat, next/core-web-vitals + next/typescript) — replaces interactive `next lint`; `npm run typecheck`; `npm run build`; `npm audit --omit=dev` as a policy gate (remediate via smallest in-range Next 15.x upgrade; any residual advisory needs documented reachability/owner/expiration — unbounded waiver fails R00).
**Docker:** build root `Dockerfile` and `apps/web/Dockerfile` (web switches to `npm ci` + lockfile COPY).
**Compose:** `docker compose config --quiet`; project A (default ports) + project B (env-overridden ports) both `up --build -d`; `python scripts/compose_smoke.py --project ...` for both (update expected alembic head to `0005`); disposable volumes; teardown step.
**Security/policy:** `python scripts/policy_scan.py` (Section K) + secret scan of repo (simple pattern scan for credentials; allowlist fixtures).
**New `.dockerignore` files:** root (`.git`, `.venv`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.data`, `node_modules`, `apps/web/.next`, `apps/web/node_modules`, `dist`, `build`, `.env*` except example, `.kilo`) and `apps/web/.dockerignore` (`node_modules`, `.next`, `.git*`).

---

## M. FILE-BY-FILE CHANGE MAP

| File | Purpose | Change type | Tests |
|---|---|---|---|
| `pyproject.toml` | wheel truth | add `scientific` to wheel packages; add `build` dev extra | `tests/contract/test_distribution.py` |
| `migrations/versions/0005_cj_r00_readiness.py` | new | schema per Section G | `tests/integration/test_migration_0005.py` |
| `packages/database/models.py` | mirror 0005 | add columns | migration + queue tests |
| `packages/database/jobs.py` | fencing + reaper | claim returns ClaimedJob+token; fenced start/heartbeat/succeed/fail; `verify_lease`; `reap_expired`; fail from claimed; failure_reason | `tests/unit/test_queue.py` (rewritten) + `tests/integration/test_job_fencing.py` (new) |
| `workers/runtime.py` | fenced adapter | ClaimedJob context; reap each poll; token in all transitions; terminal-failure hook | queue/worker integration tests |
| `workers/statistics/__main__.py` | claim artifact job | claim `run_analysis_from_artifacts`; dispatch to execution service; register failure hook | execution E2E |
| `workers/statistics/analysis.py` | dead legacy handler | **delete** | n/a (removed) |
| `workers/ingest/__main__.py` / `materialize.py` | handler signature adaptation | accept ClaimedJob (extract payload) | existing durable fixture tests |
| `packages/resources/execution.py` | **new** execution service | Section F | `tests/integration/test_analysis_execution.py` |
| `packages/statistics/registry.py` | **new** minimal registry | `cnv_rna` engine contract only | registry unit tests + execution tests |
| `scientific/crossmodal/analysis.py` | scientific correctness | duplicate-key rejection; finite eligibility before min-pairs; effective-n accounting; complete result identity fn; skip untestable genes | `tests/scientific/test_crossmodal_golden.py` (expanded) |
| `packages/schemas/finding.py` | computed payload contract | keep strict Finding; add identity helper fields if needed | scientific tests |
| `packages/schemas/resources.py` | remove caller identity | delete `FindingCreate`; add internal publication types if needed | durable resource tests updated |
| `packages/resources/service.py` | publication ownership | remove `persist_finding`; add internal `publish_findings` for execution service; consistent Analysis transitions | `tests/integration/test_durable_resources.py` updated |
| `packages/schemas/identity.py` | reusable unique | `unique_records()` | snapshot tests |
| `packages/schemas/snapshot.py` | identity version | `SnapshotRecord.identity_version` | snapshot tests |
| `workers/ingest/snapshot.py` | identity v2 | full-record hashing + conflict detection + version | `tests/unit/test_snapshot_service.py` expanded |
| `packages/gdc/client.py` | terminal access class | 401/403 → `GDCUnavailableAccess` | `tests/contract/test_gdc_client.py` |
| `packages/gdc/transfer.py` | containment | frozen-metadata requirement, BAM denial, size bound, timeout | `tests/contract/test_gdc_policy.py` expanded |
| `.github/workflows/ci.yml` | gates | jobs per Section L | CI itself |
| `.dockerignore`, `apps/web/.dockerignore` | **new** build context | excludes | docker build gate |
| `compose.yaml` | ports | `${CANCERJEV_*_PORT:-default}` host bindings | compose smoke |
| `scripts/compose_smoke.py` | head version | assert `0005`; accept port env | compose smoke |
| `scripts/policy_scan.py` | **new** | Section K scanner | `tests/contract/test_open_data_surface.py` |
| `apps/web/package.json` + lockfile + `eslint.config.mjs` | noninteractive lint + advisory remediation | eslint devDeps/config; smallest Next 15.x bump | frontend CI |
| `apps/web/Dockerfile` | reproducible build | `npm ci` + lockfile copy | docker build |
| `README.md`, `ARCHITECTURE.md`, `docs/reproducibility.md`, `workers/statistics/README.md` | current truth | post-R00 verified status only | doc review |
| `tests/**` | failing-first coverage | per Section O | — |

---

## N. IMPLEMENTATION SEQUENCE (small, independently testable units; one PR, ordered commits)

**U1 — Packaging truth (Blocker 2).**
Change: wheel includes `scientific`; `build` dev extra; wheel-content + isolated-import contract tests; CI wheel job.
Tests: `test_distribution.py` (RECORD contains scientific/apps/packages/workers; import from clean venv outside checkout).
Risk: low. Done: wheel imports all runtime modules from outside the tree.

**U2 — Fencing + migration 0005 (Blockers 5, 8; findings C5, C8, C11).**
Change: migration + models + fenced claim/start/heartbeat/succeed/fail + `verify_lease` + `failure_reason`; `fail` from claimed.
Tests: rewritten `test_queue.py` (token predicates), new PostgreSQL `test_job_fencing.py` (stale succeed, stale heartbeat same-worker, exhausted reaper), `test_migration_0005.py`.
Risk: medium (worker/runtime concurrency) — mitigated by reaper idempotence and additive schema.
Done: every job mutation proves job_id+worker_id+attempt_token; exhausted expired jobs reach terminal `failed`.

**U3 — Worker runtime integration (reaper + context + failure hook).**
Change: `ClaimedJob` context through handlers; reaper each poll; terminal-failure hook; ingest worker adaptation.
Tests: worker loop integration with PostgreSQL; crash-window (kill between claim and succeed) converges.
Risk: medium. Done: stale attempts cannot publish; no exhausted job stays active.

**U4 — Snapshot identity v2 (Blocker 3).**
Change: `unique_records`; full-record hashing; `identity_version`; v1 read compat.
Tests: conflicts raise; order invariance; v1 fixture loads; digest changes on any record field.
Risk: medium (identity churn) — new snapshots only; v1 untouched. Done: same v2 digest ⇒ same biological/access state.

**U5 — Scientific engine correctness (Blocker 4a; findings C1–C3).**
Change: duplicate-key rejection; finite eligibility before min-pairs; effective-n eligible/missing; cohort-relative missingness; untestable genes skipped (no crash).
Tests: golden results, NaN accounting, duplicate rejection, reorder invariance.
Risk: medium (changes reported numbers vs legacy) — legacy path is dead, so no consumer regression. Done: metadata population == analyzed population; duplicates fail deterministically.

**U6 — Finding identity + immutability (Blockers 4b, 7, 8).**
Change: complete result identity (Section H); remove `FindingCreate`; internal server-side publication with `unique(analysis_id, result_hash)` convergence; finding_id derivation.
Tests: identity inclusion/exclusion matrix (input hash, cohort, parameters, engine version, family, environment, output each change identity; ordering does not); caller-identity rejection; immutable rows.
Risk: medium. Done: API/worker cannot supply authoritative identity; exactly one Finding per analysis/result.

**U7 — Execution service + registry (Blockers 1, 7; finding C4).**
Change: `packages/resources/execution.py`, `packages/statistics/registry.py`, service publication wiring, Analysis/jobs consistent terminal states, idempotent replay ordering.
Tests: `test_analysis_execution.py` (File CAS + S3 parity; replay after simulated crash; corrupt/missing object → INTEGRITY_FAILURE; engine mismatch → UNSUPPORTED; snapshot/cohort lineage mismatch → INVALID_SCIENTIFIC_INPUT).
Risk: high (core vertical) — mitigated by failing-first E2E fixture before contract freeze (per CJ-R00 architecture confidence note).
Done: one immutable Finding end-to-end; consistent Analysis/Job terminal states on every failure class.

**U8 — Worker wiring.**
Change: statistics worker claims artifact job, dispatches to execution service with fenced context; delete legacy handler/job types; worker README truth.
Tests: real worker process claims API-created job → Finding appears; killed worker replaced → stale attempt cannot publish.
Risk: medium. Done: production API→worker→Finding path works; legacy inline types unclaimed.

**U9 — Acquisition containment (Blocker 6).**
Change: typed `GDCUnavailableAccess`; transfer gating (frozen open metadata, BAM denial, size bound, timeout); `scripts/policy_scan.py` + fixtures.
Tests: `test_open_data_surface.py` (auth headers, token config shapes, non-open access, 401/403 classification, full-BAM denial before network, scanner self-tests).
Risk: low. Done: no production action authenticates to GDC or downloads complete BAMs; scans green with fixtures.

**U10 — Build/CI/Compose/frontend (quality risks).**
Change: CI workflow jobs (Section L); `.dockerignore`s; compose port parameterization; web `npm ci` + eslint config + smallest Next 15.x bump; `compose_smoke` head `0005`.
Tests: CI gates themselves + two-project compose smoke.
Risk: low–medium (frontend dependency churn) — bounded by lockfile-only minimal diff.
Done: all Section P commands pass from clean checkout.

**U11 — End-to-end verification + documentation truth.**
Change: full acceptance run; update README/ARCHITECTURE/reproducibility/worker docs to verified post-R00 state; record versions/outputs.
Risk: low. Done: Section P passes; docs contain no unimplemented claims.

Sequence rationale: packaging first (unblocks verified installs), fencing before execution (publication safety), snapshot/science before execution service (identity contracts its inputs), execution before worker wiring, containment and CI last as orthogonal gates. Failing-first tests accompany each unit (CJ-R00 Phase 0 folded in per-unit).

---

## O. TEST MATRIX

| Area | File | Scenarios |
|---|---|---|
| UNIT | `tests/unit/test_queue.py` | fenced transitions require token; fail-from-claimed; reaper classification; invalid transitions |
| UNIT | `tests/unit/test_snapshot_service.py` | v2 conflict raise; exact-duplicate collapse; order invariance; v1 read; digest sensitivity |
| CONTRACT | `tests/contract/test_distribution.py` | wheel contains scientific; isolated imports; no source-tree fallback |
| CONTRACT | `tests/contract/test_open_data_surface.py` | auth-header/token/config/CLI denial; non-open access; 401/403 → UNAVAILABLE_ACCESS; complete-BAM denial pre-network; scanner fixtures |
| CONTRACT | `tests/contract/test_gdc_client.py` / `test_gdc_policy.py` | typed access failure; transfer gating; existing host/open/limit regressions |
| SCIENTIFIC | `tests/scientific/test_crossmodal_golden.py` | golden CNV/RNA; duplicate-key rejection; NaN/missingness accounting (eligible==effective n); reorder invariance; identity inclusion/exclusion matrix |
| INTEGRATION | `tests/integration/test_analysis_execution.py` | API→job→worker→Finding; File/S3 parity; replay/crash windows; corrupt/missing CAS; unsupported engine; lineage mismatch |
| INTEGRATION | `tests/integration/test_job_fencing.py` | stale completion; stale heartbeat; exhausted reaper; cancellation state machine |
| INTEGRATION | `tests/integration/test_durable_resources.py` | Cohort/Finding immutability; caller-identity rejection; legacy v1 reads; existing regressions retained |
| MIGRATION | `tests/integration/test_migration_0005.py` | fresh/legacy upgrade; downgrade guard; trigger/constraint preservation |
| FRONTEND/BUILD | CI jobs + `eslint.config.mjs` | noninteractive lint; typecheck; production build; audit policy; wheel/image/compose gates |
| NEGATIVE SECURITY | policy scan + contract tests | traversal/symlink (existing stage containment regression); oversized payloads; token-shaped fixtures; secret scan |

---

## P. MACHINE-VERIFIABLE ACCEPTANCE COMMANDS (clean checkout, Python 3.12, Node 22, Docker)

```bash
python -m pip install -e '.[dev]'
python -m ruff check .
python -m pytest -q                       # full suite incl. PostgreSQL via CANCERJEV_DATABASE_URL
python -m alembic heads                   # single head: 0005

python -m build
python -m venv /tmp/cj-wheel && /tmp/cj-wheel/Scripts/python -m pip install dist/cancerjev-*.whl
cd /tmp && /tmp/cj-wheel/Scripts/python -c "import apps.api.main, workers.ingest.__main__, workers.statistics.__main__, scientific.crossmodal, packages.statistics.registry"
python scripts/policy_scan.py

cd apps/web && npm ci && npm run lint && npm run typecheck && npm run build && npm audit --omit=dev

docker compose config --quiet
docker compose --project-name cancerjev-r00-a up --build -d
python scripts/compose_smoke.py --project cancerjev-r00-a
CANCERJEV_API_PORT=8001 CANCERJEV_WEB_PORT=3001 CANCERJEV_MINIO_PORT=9002 CANCERJEV_MINIO_CONSOLE_PORT=9003 \
  docker compose --project-name cancerjev-r00-b up --build -d
python scripts/compose_smoke.py --project cancerjev-r00-b
```

Plus (already covered by pytest, stated for the record): a `POST /v1/analyses` fixture reaches exactly one immutable Finding through the production worker with no inline matrices in the job payload; killing/replacing a worker cannot let the stale attempt publish; conflicting frozen metadata and duplicate molecular keys fail deterministically; changing any identity-bearing field changes Finding identity.

---

## Q. OUT-OF-SCOPE / DEFERRED

- CJ-R01+ cohorts/analyses product features; CJ-R04 full acquisition planner/slicer/receipts; CJ-R05 generalized manifest/engine registry; CJ-R06 runtime isolation/quotas (no end-user login — AGENTS.md §6); CJ-R07 validation firewall; CJ-R08–R12 discovery engines; CJ-R11 reproduction workflow; CJ-R13+ Jev/semantic ledger; research agents; UI expansion; optional distributed execution (R28–R32, never blocks native production); production rollout (R33).
- No Redis/Kafka/Kubernetes/new brokers/new auth/new Jev integration; no discarded Milestone A/B revival; no Python 3.13/3.14 compatibility expansion; no mypy gate; no cancel API (state machine supports `cancelled` but no producer).
- Postgres host port mapping in Compose (none today, keep it that way).

---

## R. FINAL IMPLEMENTATION CHECKLIST

- [ ] U1: `pyproject.toml` wheel includes `scientific`; `build` dev extra; `tests/contract/test_distribution.py` (failing-first) passes; CI wheel job
- [ ] U2: migration `0005` (attempt_token ×2, failure_reason, identity_version, cohort/finding triggers, `uq_findings_analysis_result`); models mirrored; fenced `claim/start/heartbeat/succeed/fail` + `verify_lease` + `reap_expired`; `fail` from claimed; `tests/integration/test_migration_0005.py` + `test_job_fencing.py` + rewritten `test_queue.py`
- [ ] U3: `workers/runtime.py` ClaimedJob context, reaper per poll, terminal-failure hook; ingest worker adapted; worker crash-window test
- [ ] U4: `unique_records` in `packages/schemas/identity.py`; v2 full-record hashing + `identity_version` in `workers/ingest/snapshot.py` + `SnapshotRecord`; v1 fixtures load; expanded `test_snapshot_service.py`
- [ ] U5: `scientific/crossmodal/analysis.py` duplicate rejection, finite-before-min-pairs eligibility, effective-n missingness, cohort-relative denominator, untestable-gene skip; expanded golden tests
- [ ] U6: complete result identity (Section H) computed server-side; `FindingCreate`/`persist_finding` removed; internal `publish_findings` with convergence; identity matrix tests; immutability + unique-constraint tests
- [ ] U7: `packages/resources/execution.py` + `packages/statistics/registry.py` (cnv_rna only); fenced in-tx Analysis transitions; idempotent replay; `tests/integration/test_analysis_execution.py` (File+S3, crash replay, corrupt CAS, engine/lineage mismatches)
- [ ] U8: statistics worker claims `run_analysis_from_artifacts`; legacy handler/types deleted; real-worker E2E + stale-worker test; worker README updated
- [ ] U9: `GDCUnavailableAccess` (401/403, retryable=false, UNAVAILABLE_ACCESS); transfer gating (frozen open metadata, BAM denial, size cap, subprocess timeout); `scripts/policy_scan.py` + `tests/contract/test_open_data_surface.py`
- [ ] U10: CI jobs (wheel, migrations, frontend, docker, compose, policy, secret); root + web `.dockerignore`; web `npm ci` + `eslint.config.mjs` + smallest Next 15.x bump; compose port env parameters; `compose_smoke.py` head `0005`
- [ ] U11: full acceptance (Section P) recorded with versions; README/ARCHITECTURE/reproducibility/worker docs updated to verified truth only
- [ ] Reviewer checklist from CJ-R00 satisfied (failing-before/passing-after per blocker; single publication owner; no caller-authoritative identity; attempt token in every mutation; snapshot v2 completeness; legacy readability; no BAM/credential route; all gates actually ran; no unrelated churn)

---

## Decisions recorded (challenge during implementation if evidence contradicts)

1. Legacy `run_analysis`/`reproduce_finding` job types are **deleted** (dead code, wrong contract), not quarantined — nothing produces them.
2. `finding_id` derives from `(analysis_id, result_hash)`; uniqueness is `unique(analysis_id, result_hash)` — per-Analysis authoritative publication; cross-Analysis reproduction semantics deferred to R11.
3. Rows are filtered to cohort membership before the engine; `cohort_size` denominator is the frozen cohort's case count.
4. The reaper runs inside the worker poll loop (no separate process/service).
5. Execution-service publication transactions verify the job fence in-transaction (strongest reading of CJ-R00 Phase 2 exit).
6. Duplicate molecular keys are rejected outright (deterministic INVALID_SCIENTIFIC_INPUT), not deduplicated — canonical materializations must not contain them.
7. Frontend advisory remediation is bounded to the smallest in-range Next 15.x lockfile change; any residual advisory needs a documented reachability/owner/expiration note.

## Open items resolvable only during implementation (no design impact)

- Exact Next 15.x patch version that clears the recorded high/moderate advisories (must be re-verified live; README baseline may be stale).
- Whether `ix_jobs_claim` suffices for the reaper query or an additional partial index is warranted (measure on real PostgreSQL).
