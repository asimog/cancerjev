# CancerJev — Full Product Implementation Plan

Based on thorough analysis of current `main` at commit `20b278af3b33245fdcc879bde3edee1d57251016`
(PRs #1–#9 merged, CJ-01 through CJ-08 proposed but not implemented).

---

## 0. Current Repository Baseline Summary

### Already Implemented (KEEP — extend, don't rewrite)

| Area | Key files | Status |
|------|-----------|--------|
| GDC REST adapter | `packages/gdc/client.py`, `filters.py`, `policy.py` | Open-only, official host, bounded, retryable |
| Logical snapshots | `workers/ingest/snapshot.py`, `packages/gdc/{identity,selection}` | Frozen identity, open discovery, manifest, coverage |
| 5 canonical parsers | `packages/gdc/parsers.py` | MAF, STAR RNA, ASCAT3 CNV, DNAcopy segments, clinical API |
| Materialization | `packages/gdc/materialization.py`, `packages/resources/materialization.py` | Verified source, canonical Parquet, lineage |
| Object storage | `packages/storage/{objects,config}.py` | File/S3 CAS, verified staging, atomic publication |
| DB models (17 tables) | `packages/database/models.py` | Snapshot → Object → Artifact → Materialization → Case/Sample/Aliquot |
| PostgreSQL queue | `packages/database/jobs.py` | SKIP LOCKED, heartbeat, lease/ownership |
| Resource service | `packages/resources/service.py` | Transactional cohorts, analyses, findings, idempotency |
| Statistics primitives | `packages/statistics/{core,endpoints,registry}.py` | BH, Pearson, Welch, frequency, variance, outliers, KM, survival endpoint |
| Engine registry | `packages/statistics/registry.py` | 10 engines with typed parameters |
| Finding v2 schemas | `packages/schemas/finding.py` | Eligibility, Correction, typed results (Frequency, CNV, Outlier, Association, Contingency, Survival, QC, NonEstimable) |
| Cross-modal prototype | `scientific/crossmodal/analysis.py` | CNV-RNA inner join (caller-supplied rows — needs artifact-backed) |
| API routes | `apps/api/main.py` | Health, projects, snapshots, cohorts, analyses, findings, GDC proxy |
| Compose environment | `compose.yaml` | API + ingest/statistics workers + PostgreSQL + MinIO + web |
| Tests | `tests/{unit,contract,integration,scientific}` | 88+ passing tests |
| Migrations | `migrations/versions/0001-0003` | Foundation → durable resources → materialization |

### NOT Implemented (gaps to fill)

| Area | Status |
|------|--------|
| Artifact-backed scientific execution | ❌ `execute_analysis` accepts caller rows, hashes, counts |
| AnalysisInputResolver | ❌ No snapshot→cohort→materialization→Parquet resolution |
| DatasetPartition/validation firewall | ❌ No discovery vs validation split |
| SearchRun / CandidateObservation | ❌ No deterministic search |
| Multiple-testing families | ❌ BH is transient — no family/test-universe persistence |
| JevService / Semantic Ledger | ❌ Old PR #2 reverted; no SDK |
| CandidateState / Jev modes | ❌ |
| DiscoveryRun / ExpansionRecipe | ❌ |
| Immutable Finding + Reproduction | ❌ Finding is mutable in DB; no reproduction |
| Block / WorkUnit / Submission | ❌ Placeholder READMEs only |
| NativeAgentRuntime | ❌ |
| Claim / Hypothesis / Evidence | ❌ |
| Evidence Graph | ❌ |
| ResearchState / Synthesis | ❌ |
| ResearchAction / WorkUnitFactory | ❌ |
| Literature retrieval / Jev reranking | ❌ |
| Researcher cockpit UI | ❌ Two source-data pages only |
| External-agent protocol | ❌ README placeholder |
| Auth/authorization | ❌ No auth |
| Jev integration | ❌ |

### Key Scientific Defects Verified in Audit

1. **Duplicate order changes scientific result** — CNV-RNA dict overwrites by (case,sample,gene); reversing input changes Pearson r from −0.43 to +0.96
2. **Input hash not in Finding hash** — changing `input_hashes` does not change Finding identity
3. **Missingness/eligibility mismatch** — NaN RNA among 6 pairs reports n=5 but Finding says 6 eligible
4. **Sample metadata not in snapshot hash** — changing sample type retains same hash
5. **Legacy `execute_analysis` accepts caller-supplied molecular rows** — no artifact resolution

---

## 1. New PR Sequence (CJ-09 through CJ-36)

Replaces old CJ-01–CJ-08 proposals. These are ordered by dependency and aligned with the five-layer / four-ledger architecture.

### MILESTONE A — TRUSTWORTHY SCIENCE FOUNDATION

---

#### CJ-09: Package correctness, reproducible builds, CI gates

**Mission:** A clean checkout has repeatable verification, the Python package can execute scientific modules outside the source directory, and CI covers the full backend stack.

**Why now:** Baseline — all later evidence depends on trustworthy tooling.

**Current facts:**
- `pyproject.toml` excludes `scientific` from wheel packages (line 39 has `"apps", "packages", "workers"` only)
- Docker build contexts lack `.dockerignore` — copies entire tree including node_modules, `.venv`, `.data`
- `apps/web/Dockerfile` ignores `package-lock.json`
- `next lint` opens interactive setup
- CI runs Ruff/pytest/PostgreSQL only — no frontend, no Compose smoke, no wheel test

**Scope:**
1. Include `scientific` in wheel packages
2. Add `.dockerignore` excluding node_modules, `.venv`, `.data`, `__pycache__`, `.env`, `.git`
3. Proper lockfile-based npm install in web Dockerfile
4. Make frontend lint noninteractive with explicit Next.js ESLint config
5. Extend CI: frontend typecheck + lint + build, wheel import verification, compose smoke test
6. Record Python/Node/Docker tool versions in CI output

**Domain/API/jobs:** No schema, route, or job changes.

**Migration:** None.

**Tests/commands:**
- `python -m ruff check .` — pass
- Full pytest suite (88+ tests) — pass
- `pip wheel --no-deps .` + import from /tmp — works
- Frontend: `npx next lint`, `npx tsc --noEmit`, `npm run build`
- Docker compose build + smoke health check
- No secrets or dependency trees in final images

**Acceptance:** Fresh checkout → install → Ruff → pytest → wheel → frontend lint/typecheck/build → Compose build all pass. Scientific import works from /tmp.

---

#### CJ-10: Freeze complete source identity and verify object publication

**Mission:** Selection-relevant metadata and canonical object bindings cannot change unnoticed under a snapshot identity.

**Why now:** Audit reproduced identical hashes after sample-type changes (scientific risk MUST FIX).

**Current facts:**
- `LogicalSnapshotService.create.unique()` silently overwrites conflicting case/sample/aliquot IDs
- Hash contains IDs/links but omits full sample metadata (type, tumor descriptor, tissue type)
- `S3ObjectStore.put_file` hashes then uploads a mutable source and trusts existing keys without re-verification
- `FileObjectStore.delete_cache_object` accepts absolute paths outside cache
- Source metadata is partly stored as global first-writer data on DatasetObject (line 63-68 of models.py)

**Scope:**
1. Introduce snapshot identity v2 that includes canonical case/sample/aliquot metadata, required file/status/relationship fields, and server-resolved policy versions
2. Reject conflicting repeated identities before deterministic deduplication. Log the conflict
3. Keep per-source/role semantics in binding records — CAS bytes can have multiple roles
4. Publish from verified stable bytes; verify existing S3 content on idempotent put. Fix `put_file` to hash after copy
5. Fix/remove unsafe cache deletion — test absolute, traversal, and symlink boundaries
6. On idempotent materialization result, verify output/diagnostics bytes still exist and match

**Domain/API/models:** Extend `DatasetSnapshot` with identity_version. Additive binding metadata only.

**Migration:** New migration for identity version. Retain v1 hashes and readable legacy snapshots.

**Tests:**
- Same UUID / different sample type → different hash
- Duplicate conflicting identities → rejection
- Multi-role same-bytes → valid
- Corrupt existing S3 object → detected
- Source mutation during upload → detected
- Cache path traversal / absolute path → rejected
- Legacy snapshot still readable

**Acceptance:** All reproduced identity/cache defects fail safely. Old snapshots readable. Concurrent publishers cannot register unverified bytes.

---

#### CJ-11: Fence job publication and recover exhausted worker attempts

**Mission:** A dead or stale worker cannot publish, and exhausted expired jobs reach an auditable terminal state.

**Why now:** Audit found expired final attempt permanently stuck in "running" (engineering risk MUST FIX).

**Current facts:**
- `claim` filters `attempt_count < max_attempts` — expired final attempt excluded forever with no reaper
- Workers commit resources before runtime checks lease ownership (materialize.py commits before succeed)
- Heartbeat uses separate thread/session but final publication is not fenced with attempt token

**Scope:**
1. Add immutable unique attempt token/fencing generation to every claim (not just hostname/PID)
2. Pass bounded execution context through trusted handlers
3. Require current unexpired attempt at final resource publication and Job/Analysis completion
4. Reap expired exhausted attempts → failed terminal outcomes, reconcile dependent Analysis states
5. Add bounded retry scheduling, explicit transient/permanent classification, payload/result byte limits
6. Keep SKIP LOCKED and existing heartbeat. Prevent heartbeat failure from silently authorizing stale publication

**Domain/API/models:** Add attempt uniqueness/fencing/retry fields. New migration.

**Tests:**
- Real concurrent claims
- Healthy worker exclusion of dead attempts
- Process death before/after source upload
- Expiry on final attempt → terminal failure
- Stale commit after reassignment → rejected
- Heartbeat outage → lease loss detected
- Duplicate completion → idempotent
- Cancellation semantics
- Retry exhaustion behavior

**Acceptance:** Exactly one authorized attempt publishes. Repeated finalization idempotent. Every exhausted expired job terminalized. Existing ingest regression passes.

---

#### CJ-12: Connect bounded GDC acquisition to canonical materialization

**Mission:** An authorized user can request a supported frozen-file subset and obtain verified materializations through a recoverable workflow.

**Why now:** Parsers exist but acquisition is disconnected — API has no acquisition/materialization routes.

**Current facts:**
- `GDCTransfer` exists but unused by any production workflow, unbundled, passes unverified `--resume` flag
- `MaterializationService.register_local_source`, `acquire_clinical_sources`, `run` are all reusable
- API has no POST/GET acquisition or materialization routes
- `gdc-client` not installed in any Docker image

**Scope:**
1. Define bounded request/status contracts selecting frozen open UUIDs and registered parser/workflow/measurement combinations; default product scope TCGA-LUAD
2. Pin/install official gdc-client in appropriate worker image; verify actual help/flags. Never use `--latest`, auth tokens, or arbitrary server overrides
3. Validate snapshot manifest membership and metadata before transfer; enforce byte/file/concurrency/time budgets and bounded subprocess output
4. Resume only same frozen identities, verify size/MD5/SHA before source registration, then enqueue parser jobs by durable IDs
5. Freeze clinical page provenance/status independently at acquisition; retain completed pages if later page fails
6. Expose per-source/materialization progress, rejected rows, and diagnostics

**Domain/API/models:** Extend source/acquisition metadata with receipt/state. New POST/GET acquisition and materialization routes.

**Tests:**
- Fake executable contract
- Interrupted transfer
- Wrong checksum/size/filename/UUID
- Unsupported workflow
- Clinical missing page
- Duplicate request
- Crash/retry/fencing
- Quota tests
- Bounded live open-file receipt (not full cohort in normal CI)

**Acceptance:** Fixture workflow runs request → source → Parquet → durable lineage with no inline payload paths. Live binary flags verified. Original parser tests pass.

---

#### CJ-13: Execute artifact-backed analyses with strict aligned contracts

**Mission:** A POSTed supported analysis is actually executed from immutable materializations and reaches a typed durable outcome.

**Why now:** Fixes the API/worker job-type mismatch. Currently `create_analysis` queues `run_analysis_from_artifacts` but statistics worker claims legacy types `run_analysis` and `reproduce_finding`.

**Current facts:**
- `create_analysis` queues `run_analysis_from_artifacts` with `{"analysis_id"}` payload only
- `workers/statistics/__main__.py` claims `run_analysis` and `reproduce_finding`, not `run_analysis_from_artifacts`
- Current `execute_analysis` takes caller-supplied `cnv_rows`, `rna_rows`, `cohort_size`, `input_hashes` — trust violation
- Duplicate dict keys overwrite silently (CNV-RNA uses dict comprehension, line 16 of analysis.py)
- No EngineRegistry dispatch on main — `analysis.py` hardcodes `engine != "cnv_rna"`
- No result schema enforcement

**Scope:**
1. Implement `AnalysisInputResolver` — resolve snapshot → cohort → required Materializations → DatasetObjects → verified Parquet. Never trust caller rows/hashes/counts
2. Register implemented engine/version/strict parameter schemas from existing `packages/statistics/registry.py`; reject unknown versions, extra parameters, unavailable engines
3. Freeze execution manifest with unit, measurement, selection, exact population, inclusions/exclusions, source/schema/normalization versions, environment
4. Define measured/descriptive/inferential/non-estimable/failed result schemas (finding.py v2 already exists)
5. Implement one bounded CNV-RNA vertical slice with exact sample/aliquot/duplicate policy, finite-value handling, consistent n/missingness
6. Enable only EXPLORATORY `AnalysisPurpose` until later gates exist
7. Claim the queued `run_analysis_from_artifacts` job type and transactionally complete Analysis/results through CJ-11 fencing
8. Disable legacy inline production dispatch; preserve legacy read compatibility

**Domain/API/models:** Extend Analysis with `purpose` field. Scientific result objects stored as bounded metadata/CAS. Job payload stays `analysis_id` only.

**Scientific rules:**
- Duplicate (case,sample,gene) rows → reject or aggregate with versioned policy
- RNA measurement type mandatory — never mix counts/TPM/FPKM/FPKM-UQ
- Same-case different-sample measurements never silently align
- Non-estimable result ≠ failure

**Tests:**
- API → queue → worker → result integration
- Duplicate order/conflict
- Mismatched sample/measurement/snapshot
- Corrupt artifact
- Missing/NaN/constant/small-n cases
- Cancellation, retry, stale publication

**Acceptance:** Durable requests finish using artifact values. Modifying caller-supplied scientific values impossible (no caller values accepted). Displayed counts match computed population.

---

#### CJ-14: Implement descriptive mutation, CNV, and RNA families

**Mission:** Registered V1 descriptive science produces honest denominators, typed outcomes, and complete test-family accounting.

**Why now:** Prototype helpers are not genome-wide scientific engines. CJ-05 gives us the artifact resolution — now we need actual engines.

**Current facts:**
- `packages/statistics/core.py` has `frequency`, `expression_variance`, `expression_outliers` — primitive only
- `scientific/mutation`, `scientific/cnv`, `scientific/expression` are empty placeholders
- `select_parser` already yields consequence, CNV workflow, 6 RNA measurements, and missing CNV
- `build_coverage` is file-availability, not eligible-denominator coverage
- `packages/statistics/registry.py` already has 10 engines defined but none implemented

**Scope:**
1. **Mutation:** Implement frequency/presence, eligible somatic counts, co-occurrence and mutual exclusivity. Use explicit assay/sample coverage, consequence classes, multi-row/variant dedupe. Never infer negative from absent MAF rows. Do not call counts TMB without callable territory
2. **CNV:** Implement ASCAT3 gene-level amplification/deletion recurrence with explicit configured threshold/ploidy limitations (amplification >= threshold, deletion <= threshold). Preserve segment data as distinct context
3. **RNA:** Implement variance/outlier summaries with declared measurement/transform/zero/MAD policy and typed insufficient-data outcomes
4. **Multiple-Testing:** Introduce shared versioned `MultipleTestingFamily`/test-disposition records. Track planned vs tested vs excluded hypotheses. Descriptive results explicitly mark p/q not applicable
5. Preserve exact eligible IDs, exclusions, workflow/normalization provenance. Bound registered gene sets and output

**Domain/API/models:** New family metadata/receipts. Existing analysis routes/job type runs these engines.

**Scientific rules:**
- All EXPLORATORY
- `MT_FAMILY_001` for mutation, `MT_FAMILY_002` for CNV, `MT_FAMILY_003` for RNA
- Family IDs never regenerated to discard unfavorable tests

**Tests (scientific golden):**
- Positive/null/descriptive fixtures
- No assay coverage → unavailable
- Duplicate transcript variants
- No events
- Missing CNV/null
- Zero/MAD edge cases
- Mixed RNA types → rejection
- Small-n
- Shuffled rows → identical result
- Family membership and correction mapping

**Acceptance:** Descriptive result never carries invented p/q. Absent coverage remains unavailable. Results and populations are order-invariant. Only implemented engines can be requested.

---

#### CJ-15: DatasetPartition + validation firewall

**Mission:** Validation data reserved before discovery cannot be accessed by discovery, semantic, agent, or ordinary researcher paths.

**Why now:** Scientifically necessary — without a holdout, no confirmatory claim is valid. Adding it after scanning would not repair leakage.

**Current facts:**
- Current snapshots cover entire cohorts; no partition/lock exists
- `FrozenSnapshotReader` and new `AnalysisInputResolver` are the access points to extend
- Current CAS credentials otherwise permit full access

**Scope:**
1. Create immutable case-level partition policy/assignment receipts before discovery. Include seed/stratification inputs, all related samples/aliquots
2. Establish physically scoped artifacts and least-privilege roles/credentials OR an equally enforceable isolation boundary. A row filter with unrestricted source access is insufficient
3. Require discovery execution to resolve only DISCOVERY partition artifacts. Deny validation previews/exports, cached query results, manifests, packet inputs through ordinary paths
4. Track prior exposure and partition consumption. Already-explored data stays DISCOVERY_ONLY
5. Define a confirmation capability contract but leave validation execution disabled until HypothesisLock exists
6. Document public-data limitation: TCGA cannot be made globally secret; enforce and audit CancerJev-mediated access

**Domain/API/models:** `DatasetPartition` table with assignment/access audit. Partition references in manifests. Jobs carry purpose and authorized partition ID.

**Migration:** New immutable versioned partition tables.

**Tests:**
- Discovery reads through API, worker, raw object hash, full-cohort artifact, export, cache
- Same-case different-sample grouping
- Deterministic assignments
- Insufficient population
- Prior exposure
- All unauthorized paths fail before reading validation bytes

**Acceptance:** All unauthorized paths fail before reading validation bytes. No lock means no confirmation. Partition receipt reproduces exactly.

---
### MILESTONE B — DETERMINISTIC SEARCH + JEV

---

#### CJ-16: SearchRun + CandidateObservation + deterministic search families

**Mission:** Implement deterministic genome-wide scan that produces typed CandidateObservations with complete test-family accounting.

**Why now:** This is Layer 1's core product — "systematically search real datasets for observations."

**Current facts:**
- No SearchRun, CandidateObservation, or deterministic search exists
- Statistics primitives are functional but not connected to genome-wide execution
- EngineRegistry exists but no search orchestration

**Scope:**
1. **SearchRun:** Create SearchRun resource — binds DatasetSnapshot, Cohort, AnalysisPurpose (EXPLORATORY), engines, parameters. Persists search provenance
2. **CandidateObservation:** Create CandidateObservation resource — binds snapshot, cohort, exact eligible population, Materializations/hashes, engine/version, parameters, deterministic outputs, missingness, QC, multiple-testing family, analysis purpose, provenance
3. **V1 families:**
   - Mutation: frequency, recurrence, co-occurrence, mutual exclusivity
   - CNV: amplification/deletion recurrence
   - RNA: variance, MAD outliers
   - Cross-modal: mutation↔RNA, CNV↔RNA, residual discordance
   - Survival: versioned clinical endpoint, KM, log-rank
   - QC: age, stage, gender, coverage, missingness, selection imbalance
4. **Residual/Discordance models:** Implement deterministic residual models where justified (especially CNV↔RNA). "Expected" means expected under a named fitted statistical model, not assumed biology
5. **Multiple-testing:** Implement correct BH families across each search family. Persist family ID, number tested, correction version
6. **Deterministic prefiltering:** Weak/noisy candidates do not reach later semantic processing. Use vectorized local DuckDB/Polars work — no thousands of per-gene GDC API calls

**Domain/API/models:** New tables: `search_runs`, `candidate_observations`, `multiple_testing_families`.

**Scientific rules:**
- CandidateObservation identity binds snapshot, cohort, eligibility, materialization/hashes, engine/version, parameters, result, QC/missingness
- No timestamp in identity
- Every executed/failed/non-estimable test disposition recorded

**Tests:**
- Golden scientific: positive, null, duplicate, missingness, small-n, multiple-testing
- Cross-snapshot materialization rejected
- Same-case different-sample rejected
- RNA measurement mismatch rejected
- Empty/non-estimable results
- Shuffled rows → same result

**Acceptance:** Genome-wide deterministic scan produces typed CandidateObservations with complete family accounting. Cross-snapshot, misaligned-sample, measurement-mismatch inputs rejected.

---

#### CJ-17: Canonical JevService + Semantic Ledger

**Mission:** One production JevService with official TypeSafe SDK, immutable evaluation records, and a test provider.

**Why now:** This is Layer 2 — "Jev judges." Old PR#2 reverted in PR#3. Must be clean-slate using official SDK.

**Current facts:**
- No `packages/jev` directory
- No SDK import, no Jev service, no evaluation table
- No CandidateState builder
- No semantic worker

**Scope:**
1. Create `packages/jev/` with client/provider adapter, service, registry, schemas, persistence, calibration
2. Only the provider adapter may import `AsyncTypeSafeClient` from `typesafe-sdk`. Pin exact compatible release
3. Implement `JevService.evaluate(request)` → immutable `JevEvaluation`
4. Create question-set registry with versioned question sets
5. Create state schemas — Noul, Choice, Score primitives
6. Create policy versioning — thresholds never hidden in question prose
7. Create explicit test provider with deterministic fixture responses. No production fallback from test provider
8. Add bounded process-level concurrency — reuse lifecycle-managed client
9. Add readiness diagnostics using `models.list()` where appropriate

**JevEvaluation schema binds:**
- purpose, subject type/ID, state schema/version/hash
- question-set ID/version, policy version
- requested model, resolved model, SDK/provider version
- complete typed answers, probability distributions
- Choice/Score confidence where actually returned
- usage, error/provider metadata, timestamps
- Multiple attempts preserved (not overwritten)

**Domain/API/models:** New tables: `jev_evaluations`, `jev_attempts`. No scientific promotion logic.

**Migration:** New migration for Jev tables.

**Tests:**
- Noul, Choice, Score
- Mixed independent questions
- Retries
- 429, timeout
- Malformed response
- Unavailable provider
- Model resolution
- Concurrency
- Secret redaction

**Acceptance:** Official SDK integrated with test provider. Immutable evaluations persisted. No scientific authority.

---

#### CJ-18: CandidateState + SHAPE_ONLY / CONTEXTUAL Jev modes

**Mission:** Build CandidateState from deterministic CandidateObservations and evaluate with explicit Jev modes.

**Why now:** Connects Layer 1 → Layer 2. SHAPE_ONLY is a bias-control tool, not just a feature.

**Current facts:**
- No CandidateState exists
- No precomputed semantic-safe fields
- No mode distinction

**Scope:**
1. `CandidateState` builder — precomputes semantic-safe fields from CandidateObservation:
   - `statistical_state`: multiple-testing passed, minimum_n, estimable, effect magnitude band
   - `pattern`: type, direction, discordant subgroup
   - `quality`: missingness band, batch flag, selection flag
   - `audit_values`: n, effect, q (for audit — never asked to arithmetic)
2. `SHAPE_ONLY` mode: pseudonymize gene/feature identity. No literature/prior biological knowledge. Emphasize qualitative deterministic state.
3. `CONTEXTUAL` mode: real feature identity and intentionally supplied biological context
4. Domain-specific atomic question sets:
   - structural discordance?
   - underexplained state?
   - artifact suspicion?
   - subgroup shape?
   - more deterministic analysis useful?
5. Prefer Noul for independent attributes. Use Choice only for mutually exclusive. Use Score only if benchmarked ordinal
6. Do not ask Jev to compute p, q, N, ratios, residuals, or dates

**Scientific rules:**
- Jev may NOT:
  - calculate p/q
  - count patients
  - calculate ratios
  - perform numeric normalization
  - decide Finding statistical validity
  - define scientific replication
  - convert confidence into "probability hypothesis is true"
  - advance scientific status by itself

**Benchmarks:** Per question-set and per-mode calibration. No universal 0.8 gate.

**Tests:**
- Obvious discordance
- Null/ordinary
- QC suspect
- Subgroup pattern
- Insufficient state
- Adversarial/irrelevant state
- Blinded famous-gene controls
- All precomputed values present in state

**Acceptance:** CandidateState produced from deterministic CandidateObservations. Jev answers bounded semantic questions. No arithmetic/statistical inference by Jev.

---

#### CJ-19: Jev-guided bounded adaptive search (DiscoveryRun + ExpansionRecipe)

**Mission:** Allow Jev semantic signals to guide where deterministic compute is spent — within explicit budgets and always EXPLORATORY.

**Why now:** The core adaptive loop of CancerJev. "Jev may influence attention and routing."

**Current facts:**
- No DiscoveryRun, ExpansionRecipe, DiscoveryPolicy, or compute budget exists
- No routing code

**Scope:**
1. **DiscoveryRun:** Create DiscoveryRun resource — binds CandidateObservation, lineage of expansions, routing decisions, eventual Finding
2. **ExpansionRecipe registry:** Server-owned deterministic code. Initial recipes:
   - Stage stratification
   - Age stratification
   - Gender stratification
   - Mutation context
   - CNV context
   - Segment-CNV context
   - Survival association
   - Missingness/coverage audit
   - Sample-selection audit
   - Clinical-composition audit
3. **IMPORTANT routing design:** Multiple follow-ups can be simultaneously useful. Default router uses one atomic Noul relevance question per eligible ExpansionRecipe, evaluated together against same state. CancerJev code combines: Jev relevance, confidence, data availability, already-run status, cost, search budget, holdout/validation leakage restrictions
4. **DiscoveryPolicy:** Versioned thresholds, budgets, routing rules
5. **Bounded:** depth, expansions per candidate, total analyses, Jev calls, wall time/cost
6. Every selected route executes through artifact-backed engine (CJ-13). New deterministic results → new immutable CandidateState

**Critical rule:** Jev does NOT promote scientific truth. Finding creation must satisfy deterministic scientific policy. Different Jev outputs over identical deterministic data must not change scientific result hash.

**Domain/API/models:** New tables: `discovery_runs`, `expansion_recipes`, `discovery_policies`.

**Tests:**
- Route relevance
- Multi-route scheduling
- Budget exhaustion
- Provider failure
- Deterministic failure
- Idempotency
- No arbitrary execution paths

**Acceptance:** Jev-guided expansion routes are EXPLORATORY. Different Jev outputs → same deterministic Finding identity. Budgets enforced.

---

#### CJ-20: Immutable Finding + Reproduction + DiscoveryTrace

**Mission:** Make Finding a first-class immutable reproducible scientific object with complete deterministic provenance and exact historical reproduction.

**Why now:** Currently Finding is mutable in DB (no immutability trigger) with generic payload. Reproduction alias is just the legacy row handler.

**Current facts:**
- Finding table lacks DB immutability trigger
- `persist_finding` checks ID/hash but no DB-level protection
- `reproduce_finding` = `execute_analysis` alias
- No DiscoveryTrace exists

**Scope:**
1. **Finding v2:** Persist complete deterministic provenance:
   - DatasetSnapshot, Cohort/hash
   - Exact eligible case/sample IDs
   - Materialization IDs, object hashes
   - Parser/schema/normalization/selection versions
   - Engine/version, parameters, measurement type
   - Correction family, endpoint version
   - Code commit, deterministic seed, dependency/environment fingerprint
2. **Scientific result hash:** Includes deterministic science only. Excludes JevEvaluation, model confidence, DiscoveryRun priority, agent output, timestamp, worker hostname
3. **ReproductionRun:** POST reproduction with Finding ID only. No caller molecular rows. Resolve exact historical inputs and engine. States: IDENTICAL, MISMATCH, FAILED, UNAVAILABLE_VERSION
4. **DiscoveryTrace:** Capture SearchRun → CandidateObservation → CandidateState(s) → JevEvaluation(s) → ExpansionRecipe(s) → routing → eventual Finding. Preserves discovery provenance without contaminating scientific identity
5. Make Finding immutable; corrections use supersession/retraction resources
6. Never silently substitute newer engine version in reproduction
7. Produce field-level mismatch reports

**Domain/API/models:** New tables: `finding_reproduction`, `discovery_trace`. Add DB immutability trigger to findings. New versions column.

**Migration:** Add immutability trigger. Backfill legacy findings as "incomplete".

**Tests:**
- Hash stability: same inputs → same hash
- Changed membership → different hash
- Changed input → different hash
- Changed parameters → different hash
- Different Jev answer → same hash
- Corrupt source → reproduction FAILED
- Exact reproduction → IDENTICAL
- Unavailable engine → UNAVAILABLE_VERSION
- Immutability enforced at DB level
- Supersession/retraction works

**Acceptance:** Reproducible from snapshot + IDs. Different Jev → same scientific hash. Engine unavailable → honest failure.

---
### MILESTONE C — NATIVE CLOSED-LOOP CANCERJEV

---

#### CJ-21: Research domain — Block, WorkUnit, WorkAssignment, EvidencePacket

**Mission:** Implement the core research contracts that native and external agents will share.

**Why now:** Native first, distribution-ready from day one. Same contracts for both.

**Current facts:**
- `workers/research/README.md`, `workers/validation/README.md`, `clients/cancerjev-agent/README.md` are placeholders
- No Block, WorkUnit, Submission, EvidencePacket, AgentRuntime
- Internal Job is not suitable as public protocol

**Scope:**
1. **Block:** Active scientific investigation state. Tracks Block status, active hypotheses, unresolved Claims, evidence gaps, outstanding WorkUnits, replication targets, convergence state, compute budget, validation status, human-review state, closure criteria
2. **WorkUnit:** Immutable task identity. Contains ID/version, Block, purpose, instructions, EvidencePacket hash, source/tool policy, CLOSED_EVIDENCE or OPEN_RESEARCH mode, expected output schema, protocol version, replication target, creation lineage
3. **WorkAssignment:** Separate mutable resource from WorkUnit. Contains agent ID, attempt token, lease expiry, completion status
4. **WorkLease:** Renewable lease with ownership, expiry, reclaim
5. **EvidencePacket:** Bounded authorized data and provenance — Finding IDs, exact statistics, QC/confounders, reproduction state, deterministic graph context, vetted literature passages. No raw matrices
6. **AgentRuntime protocol:** `execute(work_unit, packet) -> Submission` shared interface
7. **Initial WorkUnit types:** HYPOTHESIS, SKEPTIC, CONFOUNDER, EVIDENCE, EXPERIMENT

**Domain/API/models:** New tables: `blocks`, `work_units`, `work_assignments`, `work_leases`, `evidence_packets`.

**Migration:** New migration for research tables.

**Scientific rules:**
- EvidencePacket never contains validation data
- Raw matrices never in WorkUnit payloads
- CLOSED_EVIDENCE mode receives frozen EvidencePacket only, no live literature/tools

**Tests:**
- Block lifecycle
- WorkUnit creation
- WorkAssignment claim/release
- Lease ownership/expiry/reclaim
- EvidencePacket bounds
- Cross-agent contract consistency

**Acceptance:** WorkUnit, EvidencePacket, WorkAssignment contracts defined and tested. Native and external agents will share same Submission envelope.

---

#### CJ-22: Native CancerJev research agent

**Mission:** Implement NativeAgentRuntime that produces structured Submissions from WorkUnits and EvidencePackets.

**Why now:** The actual Layer 3 execution. No special privileged path.

**Current facts:**
- No agent runtime exists
- No research model provider adapter
- `workers/research/` is README placeholder

**Scope:**
1. **ResearchModelProvider** abstraction — one adapter for configured research model. Separate from Jev provider
2. **NativeAgentRuntime:** `AgentRuntime.execute(work_unit, packet) -> Submission`
   - Receives EvidencePacket, produces structured Submission with atomic Claims
   - Uses configured ResearchModelProvider
   - Output remains untrusted reasoning until validated
3. **Submission schema:** immutable WorkUnit/packet/assignment identity, structured Claims/critiques/predictions, source/result references, declared provider/model/harness/tool metadata
4. Native agent uses exact contracts that future external agents will use. No privileged bypass
5. All outputs remain reasoning until validated. No direct ledger/DB mutation

**Domain/API/models:** New tables: `submissions`, `agent_runs`.

**Tests:**
- Submission schema validation
- EvidencePacket integrity check
- Malformed generation rejection
- No secret/matrix leakage in submission
- Provider failure handling
- Idempotent submissions

**Acceptance:** Native agent produces structured Submission from WorkUnit + EvidencePacket. Same protocol as future external agents.

---

#### CJ-23: Deterministic submission validation + Jev semantic verifier

**Mission:** Two-stage verifier — deterministic checks first, then Jev semantic verification.

**Why now:** Stage 1 prevents Jev from ever seeing fabricated IDs/numbers/citations. Stage 2 evaluates semantic claim-evidence relationships.

**Current facts:**
- No submission validation exists
- No verification pipeline

**Scope:**
1. **Stage 1 — Deterministic:**
   - WorkUnit ownership/lease
   - EvidencePacket hash integrity
   - Claim schema validity
   - Evidence ID existence
   - Numerical claim against Finding values ("72/500" vs Finding "31/500")
   - Gene/case/sample identity existence
   - Cited publication/source existence (PMID/PMCID/DOI)
   - Quoted text exact/normalized existence in source
   - Replay/idempotency
   - Byte limits
2. **Stage 2 — Jev semantic:**
   For each atomic Claim and referenced evidence, create bounded state:
   - Does this evidence address the Claim?
   - Causal language stronger than supplied evidence?
   - Does cited passage support the Claim?
   - Does it contradict?
   - Is alternative still compatible?
   - Does proposed experiment directly test prediction?
   - Use Choice: SUPPORTS / CONTRADICTS / DOES_NOT_ADDRESS / MIXED_OR_AMBIGUOUS
   - Use Nouls for distinct additional semantics
3. **Confidence gates:** auto-accept, hold/review, escalate. Never use Jev confidence as scientific confidence
4. Persist every verification event — submission state through deterministic → semantic → outcome

**Scientific rules:**
- Jev must never be asked whether arithmetic matches
- Stage 1 failure never reaches Jev
- Never let Jev rescue fabricated citation

**Tests:**
- Fabricated quote → rejected
- Correct quote / wrong Claim → held
- Causal overstatement → flagged
- Unsupported evidence → held
- Low confidence → held
- Provider unavailable → pending
- Deterministic rejection before Jev
- Citation doesn't exist → rejected

**Acceptance:** Fabricated evidence IDs/numbers/citations rejected deterministically before Jev evaluation. Jev verifier checks semantic relationships only. All verification events persisted.

---

#### CJ-24: Claims, Predictions, Evidence, Evidence Graph, Lineage

**Mission:** Implement the core research evidence model with explicit Claim decomposition and deterministic dependency tracking.

**Why now:** Evidence attaches to atomic Claims, not broad prose. Agents propose explanations; evidence decides.

**Current facts:**
- No Claim, Hypothesis, Prediction, Falsifier, Evidence, EvidenceRelation, EvidenceLineage tables
- Finding is the only evidence-like resource
- No graph generation

**Scope:**
1. **Hypothesis:** Composition of atomic Claims with proposed mechanism
2. **Claim:** Atomic assertion. Examples: "Amplification is present", "Amplified subgroup shows low RNA", "Methylation is increased in subgroup", "Association persists after confounder adjustment"
3. **Prediction:** Testable prediction derived from Hypothesis. Example: "Within amplified samples, higher methylation predicts lower RNA"
4. **Falsifier:** What would disprove the Claim/Hypothesis
5. **ScientificEvidence:** Verified empirical artifact/result with provenance and applicability
6. **EvidenceRelation:** Source–Claim relation. Persists semantic provenance to JevEvaluation where Jev was used
7. **EvidenceLineage:** Dependency tracking — same snapshot, same cohort, same publication, same experiment, same upstream dataset. Do not invent statistical independence
8. **Graph generation:** Reproducible from fixed input records. Build staging → validate → atomically activate. Same records + same builder version = same logical graph
9. **Deduplication:** Ten agents citing one Finding = one scientific evidence source. Two papers reusing same TCGA cohort = not independent

**Scientific rules:**
- Never collapse Jev support probability into Claim confidence
- Evidence deduplication is not deletion of disagreement
- Contradictory evidence stays visible

**Domain/API/models:** New tables: `hypotheses`, `claims`, `predictions`, `falsifiers`, `scientific_evidence`, `evidence_relations`, `evidence_lineages`, `evidence_graphs`.

**Tests:**
- Claim decomposition
- Evidence relation SUPPORTS/CONTRADICTS
- Evidence dedup (10 agents, 1 Finding → 1 source)
- Shared-cohort dependence tracking
- Graph generation: same records = same graph
- Graph generation: different records = different graph
- Failed generation isolation

**Acceptance:** Evidence attaches to atomic Claims. No one-global-confidence-score. Dependencies tracked. Deterministic graph generation.

---

#### CJ-25: Scientific Synthesis Layer — ResearchState, ResearchAction, WorkUnitFactory

**Mission:** Implement the fourth ledger (Synthesis) that combines scientific, semantic, and reasoning records into a bounded ResearchState, then generates next ResearchActions.

**Why now:** This is the product — "CancerJev identified this specific next analysis as the most informative computational test."

**Current facts:**
- No ResearchState, SynthesisGeneration, SynthesisPolicy
- No ResearchAction, WorkUnitFactory
- No next-research engine

**Scope:**
1. **ResearchState:** Reproducible from Scientific Ledger generation + Semantic Ledger generation + Reasoning Ledger generation + Evidence Graph generation + SynthesisPolicy version + Jev evaluations + human decisions
   - block_id, generation, scientific_status
   - active_hypotheses, weakened_hypotheses, falsified_hypotheses
   - unresolved_claims, resolved_claims
   - active_contradictions, major_evidence_gaps
   - candidate_next_tests, candidate_next_work_units, candidate_human_actions
   - validation_status, replication_status, wetlab_handoff_status
   - block_status, closure_reason
2. **SynthesisPolicy:** Deterministic over fixed verified ledger/graph inputs + explicitly referenced Jev evaluations + human decisions
3. **ResearchAction:** Typed action with preconditions, rationale, budget, approval requirements:
   - RUN_ANALYSIS, CREATE_WORK_UNIT, SEARCH_LITERATURE, REQUEST_REPLICATION
   - REQUEST_SKEPTIC_REVIEW, REQUEST_CONFOUNDER_REVIEW, REQUEST_PATHWAY_REVIEW
   - REQUEST_EXPERIMENT_DESIGN, REQUEST_HUMAN_REVIEW, PROPOSE_WETLAB_HANDOFF
   - HOLD_BLOCK, CLOSE_BLOCK, REOPEN_BLOCK
4. **WorkUnitFactory:** Bridge from approved ResearchAction to WorkUnit creation
5. Jev can help assess — Claim unresolved? evidence conflicting? test discriminating? Result still belongs to deterministic policy
6. Budget exhaustion/insufficient data is operational, not falsification

**Domain/API/models:** New tables: `research_state`, `synthesis_generations`, `research_actions`, `work_unit_factories`.

**Tests:**
- ResearchState reproducibility from fixed inputs
- Adding new evidence → same generation or new generation
- ResearchAction proposal with preconditions
- Budget exhaustion → HOLD_BLOCK not falsification
- Stale state cannot enqueue duplicate follow-ups

**Acceptance:** ResearchState built from four ledgers. ResearchAction generated with typed recipes. WorkUnitFactory creates WorkUnits from approved actions. Second deterministic test demonstrated: state → action → new test → updated state.

---

#### CJ-26: HypothesisLock + validation execution + scientific status engine

**Mission:** Enable confirmatory tests against reserved validation data with immutable HypothesisLock and deterministic scientific-status transitions.

**Why now:** Without this, all analyses remain DISCOVERY_ONLY.

**Current facts:**
- No HypothesisLock, confirmation capability, or validation execution
- No ScientificStatusTransition
- Partition exists (CJ-15) but cannot be consumed

**Scope:**
1. **HypothesisLock:** Freezes hypothesis, atomic Claims, direction, endpoint, analysis plan, statistical test, expected prediction, validation source/partition, snapshot/cohort identities, lock hash, lock time before validation access
2. **Validation execution:** Confirmatory engine accesses validation partition only after lock. Consumption tracked per lock
3. **ScientificStatusTransition:** Evidence-controlled state machine:
   - DISCOVERY_ONLY (default)
   - INTERNAL_HOLDOUT_SUPPORTED (validation confirms expected direction)
   - INDEPENDENTLY_REPLICATED (external data with separate lineage)
   - FUNCTIONAL_SUPPORT (only if relevant functional data exists)
   - MECHANISTIC_SUPPORT (only if relevant mechanistic data exists)
   - WEAKENED (evidence contradicts or fails to support)
   - FALSIFIED (precise prediction fails)
4. Implement only statuses with actual evidence types. Never fake FUNCTIONAL_SUPPORT
5. Agent/Jev votes cannot advance status — only policy + qualifying evidence
6. Replication requires separately verified lineage policy

**Domain/API/models:** New tables: `hypothesis_locks`, `validation_receipts`, `scientific_status_transitions`.

**Tests:**
- Lock immutability
- Pre-lock validation access → rejected
- Same-lock repeat → idempotent
- Retuning against revealed outcomes → rejected
- Direction mismatch → WEAKENED
- Falsification
- Agent/Jev cannot advance status
- Cross-snapshot replication rejection

**Acceptance:** Locked hypothesis can access validation partition. Evidence-controlled status transitions. No status advancement by agent/Jev votes.

---

#### CJ-27: Native full-loop local E2E

**Mission:** Prove the complete native CancerJev loop with fixture providers in normal CI.

**Why now:** Definition of "native CancerJev works."

**Current facts:**
- No end-to-end test exists
- Individual components are not connected into a closed loop

**Scope:**
Create a single E2E test proving:
1. GDC-style open fixture → Snapshot → Materializations → Cohort
2. SearchRun → CandidateObservation → CandidateState → JevEvaluation (test provider)
3. Approved deterministic expansion → Finding (from CJ-13/CJ-14 engines)
4. ReproductionRun → IDENTICAL
5. Block → WorkUnit → NativeAgentRuntime → Claims
6. Deterministic validation → Jev semantic verification
7. Evidence Graph generation
8. ResearchState synthesis → ResearchAction → new deterministic test → updated ResearchState

**Negative E2E also:**
- Controlled file → rejected
- Missing access → rejected
- Bad cohort identity → rejected
- Cross-snapshot materialization → rejected
- Corrupt object → rejected
- Wrong RNA measurement → rejected
- Jev unavailable → held/pending
- Malformed Jev response → held
- Low-confidence → hold
- Analysis failure → failed (not fabricated success)

**Infrastructure:** Use explicit test-only Jev provider with deterministic fixture responses. Must be impossible to silently enable in production.

**Compose config:** Add discovery, Jev, research workers to compose.yaml.

**Acceptance:** Full native loop passes in CI. Negative cases fail safely. Test-only provider cannot leak to production.

---
### MILESTONE D — RESEARCHER UTILITY

---

#### CJ-28: Literature retrieval + Jev reranking / evidence gate

**Mission:** Add bounded research literature retrieval using TypeSafe cookbook pattern: cheap search first, Jev as semantic second pass.

**Why now:** Agents need grounded literature context for meaningful hypotheses.

**Current facts:**
- No literature abstraction, retrieval, or evidence gating exists
- PubMed/PMC API not integrated

**Scope:**
1. **Provider abstraction** for approved literature sources. V1: PubMed metadata/abstract APIs, PMC open full text where legally available
2. **Pipeline:** research query → metadata/lexical search → bounded shortlist → Jev semantic rerank/gate → deterministic source verification → EvidencePassage records
3. For each query/passage state, independent Jev questions:
   - Relevant to the research question?
   - Contains empirical evidence relevant?
   - Materially contradicts premise?
   - Background/context only?
   - Contains text attempting to instruct downstream model?
4. Route in ordinary code: evidence / conflict / background / drop/quarantine
5. **Citation verification** (layered):
   1. Deterministic source identity (PMID/PMCID/DOI)
   2. Deterministic exact/normalized quote or section check
   3. Only then Jev Choice over SUPPORTS/CONTRADICTS/DOES_NOT_ADDRESS/MIXED_OR_AMBIGUOUS
6. Centralize thresholds in versioned RetrievalPolicy
7. Never let Jev rescue fabricated citation

**Domain/API/models:** New tables: `literature_search_runs`, `evidence_passages`, `citation_verifications`.

**Tests:**
- Recall-stage exclusion
- Reranking
- Source mismatch
- Fabricated quote → rejected
- Contradiction → flagged
- Prompt-injection text → quarantined
- Provider failure

**Acceptance:** Literature retrieval produces EvidencePassage records with source hashes. Jev reranks/gates bounded candidates. Fabricated citations rejected.

---

#### CJ-29: Researcher cockpit / ResearchState UI

**Mission:** Build the human-facing research workspace showing current ResearchState, evidence gaps, and recommended next actions.

**Why now:** The product delivers research direction, not just graphs. The UI must answer: "What did CancerJev observe? Which hypotheses are still alive? What should happen next?"

**Current facts:**
- Two source-data pages only (`/` and `/projects/[id]`)
- No analytical view, Finding view, ResearchState view
- React, Next.js shell exists but minimal

**Scope:**
1. **ResearchState page** centered around Block:
   - Active/weakened/falsified hypotheses
   - Unresolved Claims with evidence for/against
   - Evidence gaps and contradictions
   - Current scientific status (DISCOVERY_ONLY, etc.)
   - Validation/replication status
   - Next recommended actions with rationale
   - Action execution status
2. **Finding detail page:**
   - Scientific provenance (snapshot, materialization hashes, parser versions)
   - DETERMINISTIC section: N, effect, CI, p, q, missingness, QC
   - SEMANTIC section: Jev state mode, question-set/model, probabilities/confidence, routing
   - Discovery provenance (SearchRun → CandidateObservation → expansions)
   - Reproduction status
   - Finding Graph neighbors
3. **Coverage and QC views:**
   - Modality coverage
   - Missingness summary
   - Confounder summary
4. **HumanResearchDecision:** Approve/reject next action, add external evidence, lock hypothesis, close/reopen Block. All decisions append-only and auditable
5. Separate clearly: tested-and-negative / not tested / unavailable / non-estimable / Jev pending / analysis failed
6. Never display one overall "confidence" score

**Tests:**
- Component tests
- Accessibility baseline
- TypeScript strict
- Production build

**Acceptance:** ResearchState page shows current investigation state with evidence gaps and recommended actions. Human decisions auditable. Scientific vs semantic clearly distinguished.

---

#### CJ-30: Wet-lab / external research handoff

**Mission:** Produce structured ResearchHandoffPackage for external researchers.

**Why now:** CancerJev should help researchers decide what experiment is maximally informative.

**Current facts:**
- No handoff mechanism exists

**Scope:**
1. **ResearchHandoffPackage:** Freezes:
   - Research question
   - Leading hypotheses with evidence for/against
   - Competing hypotheses
   - Atomic Claims
   - Predicted outcomes
   - Falsifiers
   - Proposed experiment with required controls
   - Computational provenance
   - Replication status
   - Literature evidence
   - What result would change CancerJev's state
2. Result ingestion — external experimental results can be uploaded with source provenance and reviewer credentials
3. Explicit wet-lab status tracking

**Tests:**
- Handoff package content integrity
- Result ingestion validation
- State update from external evidence
- Cross-contamination protection

**Acceptance:** Handoff package produced from ResearchState. External results ingested. State updated based on qualified evidence.

---
### MILESTONE E — FOLDING@HOME-STYLE DISTRIBUTED NETWORK

---

#### CJ-31: Secure external-agent API + contributor client

**Mission:** Implement the external contributor protocol without giving agents infrastructure access.

**Why now:** Distribution-ready contracts (CJ-21) exist — now expose them securely.

**Current facts:**
- `clients/cancerjev-agent/README.md` placeholder
- No external API routes exist
- No credential system

**Scope:**
1. **API routes:**
   - POST /v1/agents/register
   - GET /v1/agents/{id}/capabilities
   - POST /v1/work-units/claim
   - POST /v1/work-units/{id}/heartbeat
   - POST /v1/work-units/{id}/submit
   - POST /v1/work-units/{id}/release
   - GET /v1/blocks/{id}
2. **Auth:** Hashed revocable agent credentials. Plaintext key shown only at creation, never stored
3. **WorkAssignment:** Renewable leases, ownership, expiry, reclaim. Replay protection, idempotency
4. **Security:**
   - External agents receive only Block, WorkUnit, bounded EvidencePacket
   - NEVER: database credentials, R2/S3 credentials, TypeSafe key, research-model key, filesystem paths, raw genomic matrices
   - Server never executes contributor code
   - Body limits, citation/evidence limits, quotas/rate limits, capability filtering, audit events
5. **Python client** under `clients/cancerjev-agent/`:
   - register/config
   - claim
   - heartbeat
   - submit
   - release
   - capabilities

**Domain/API models:** New tables: `agents`, `agent_credentials`, `agent_capabilities`.

**Tests:**
- Agent registration
- WorkUnit claim
- Lease expiry/reclaim
- Duplicate submission rejection
- Replay protection
- Invalid ownership
- Malformed payload
- Oversized payload
- Capability mismatch
- No DB/credentials leak

**Acceptance:** External agent can claim WorkUnit, submit results through validated API. No infrastructure access. Server never executes contributor code.

---

#### CJ-32: Distributed scheduler + replicated work units

**Mission:** Implement replication targets, diversity constraints, and completion policies.

**Why now:** After external agent API exists, need intelligent scheduling.

**Current facts:**
- No replication mechanism
- No diversity tracking
- No completion policy

**Scope:**
1. **Replication target:** WorkUnits declare `replication_target` (1, 3, 5, etc.) based on importance, uncertainty, adversarial need, benchmark requirements
2. **WorkReplica:** Distinct from retry. Multiple agents can claim same WorkUnit
3. **Diversity constraints:** Track provider, model family, model version, agent harness, system prompt/protocol, tool availability, Jev version, external data access. Scheduler enforces diversity — avoid assigning all replicas to same model
4. **Completion policy:** Not "N agents answered therefore truth." Completion means sufficient reasoning coverage, required diversity, validation passed, synthesis indicates further reasoning low-value
5. **Scheduler config:** Budgets, concurrency, assignment history, reassignment rules

**Tests:**
- Replication target enforcement
- Diversity constraints
- Reassignment on lease loss
- Expiry
- Completion policy
- Budgets

**Acceptance:** Multiple agents can claim same WorkUnit. Diversity enforced. Completion determined by policy, not vote count.

---

#### CJ-33: CLOSED vs OPEN research modes

**Mission:** Implement and enforce CLOSED_EVIDENCE and OPEN_RESEARCH modes.

**Why now:** Reproducibility and benchmarking require controlled conditions.

**Current facts:**
- No mode distinction exists
- Agent runtime has no sandbox constraints

**Scope:**
1. **CLOSED_EVIDENCE:** Agent receives only frozen EvidencePacket. No live literature, no external tools. Enforceable in native controlled runtime. For remote contributors: declared protocol mode
2. **OPEN_RESEARCH:** Agent may use approved tools/sources: PubMed, Reactome, UniProt, other approved APIs. Record: model, provider, agent harness, tool set, protocol version, Jev usage, external sources accessed
3. **Record all tool access** — which sources queried, what was retrieved, with what parameters
4. **Never compare CLOSED and OPEN performance as equivalent benchmarks**

**Tests:**
- CLOSED mode enforcement in native runtime
- OPEN mode tool tracking
- Cross-mode comparison protection in benchmarks

**Acceptance:** CLOSED_EVIDENCE mode enforced. OPEN_RESEARCH mode tracks tool usage. Benchmarks separate modes.

---

#### CJ-34: Hidden benchmark engine + capability profiles

**Mission:** Evaluate agent performance on hidden benchmark WorkUnits before frontier contributions affect synthesis.

**Why now:** Without benchmarks, we cannot distinguish capable from unreliable agents.

**Current facts:**
- No benchmark system exists
- No agent capability profiles

**Scope:**
1. **BenchmarkTask:** Hidden WorkUnit with known correct answer. Categories:
   - Known cancer drivers
   - Known passengers
   - Batch artifacts
   - Purity confounding
   - False causal interpretations
   - Evidence-support relation
   - Citation grounding
   - Pathway reasoning
   - Confounder recognition
   - Experiment discriminativeness
   - Unsupported-claim rate
   - Falsifier quality
2. **BenchmarkResult:** Per-dimension scores + summary
3. **Capability dimensions:** numerical fidelity, citation grounding, confounder detection, artifact detection, causal discipline, pathway reasoning, evidence grounding, falsifier quality, experiment design, unsupported-claim rate
4. **No one-number "Agent Score"** — publish capability profile
5. **Hidden benchmark injection:** Benchmark tasks mixed into normal WorkUnit stream. Agents don't know which are benchmarks
6. **Blinded gene tasks** for SHAPE_ONLY where appropriate

**Tests:**
- Benchmark injection
- Score computation
- Profile generation
- Leakage protection (benchmark results not visible to agents)

**Acceptance:** Benchmark tasks injected into work stream. Multi-dimensional capability profiles produced. No one-number agent quality score.

---

#### CJ-35: ConvergenceSummary + adaptive block scheduling

**Mission:** Cluster submissions, measure agreement/disagreement, and stop redundant reasoning when further work is low-value.

**Why now:** Without convergence tracking, agents can generate infinite WorkUnits.

**Current facts:**
- No convergence mechanism
- No clustering/deduplication

**Scope:**
1. **ConvergenceSummary:** Number of valid submissions, mechanism clusters, alternatives, unresolved areas, model-family diversity, disagreement map
2. **Hypothesis/Claim deduplication:** Generate cheap candidate pairs first (same gene, same pathway, lexical/embedding similarity), then Jev semantic alignment
3. **Contradiction finder:** Claim → cheap evidence retrieval → candidate contradictory passages → Jev assessment. Never all-pairs Evidence×Evidence Jev calls
4. **Adaptive scheduling:** Based on convergence — request skeptic review, stop redundant reasoning, select scientific test, escalate
5. **Convergence never advances scientific status**

**Tests:**
- Hypothesis dedup
- Contradiction detection
- Convergence threshold behavior
- Stale WorkUnit retirement

**Acceptance:** ConvergenceSummary produced from submissions. Redundant reasoning stopped. Contradictions surfaced. No convergence-based scientific promotion.

---

#### CJ-36: BYO Model / BYO Jev contributor support

**Mission:** Allow external contributors to use their own model/Jev setup.

**Why now:** Broadest possible contributor base for distributed research.

**Current facts:**
- No BYO support exists
- All model calls go through server-side providers

**Scope:**
1. **Contributor local model config:** Contributor configures their own model endpoint locally
2. **Contributor local Jev:** Optional, noncanonical. Participant Jev trace stored separately
3. **Canonical CancerJev Jev rerun:** Server reruns its own Jev evaluation on submission. Participant and canonical traces stored separately. Neither is scientific truth
4. **Metadata/versioning:** Participant declares provider, model, Jev version, harness, protocol. Server records declarative metadata
5. **No contributor API keys stored on server.** Keys remain local

**Tests:**
- BYO submission flow
- Participant vs canonical Jev trace distinction
- No key leakage
- Declared metadata integrity

**Acceptance:** External contributor can use local model/Jev. Server stores both participant and canonical traces. Neither treated as scientific truth.

---
### MILESTONE F — PRODUCTIONIZATION

---

#### CJ-37: Production auth + deployment configuration

**Mission:** Make the locally complete V1 deployable to staging/production architecture.

**Why now:** Current API has no auth, no environment separation, no deployment config.

**Target architecture:**
- Vercel: Next.js web
- Railway or equivalent: FastAPI + workers (ingest, statistics, discovery, research, synthesis, validation, scheduler)
- Supabase: PostgreSQL + researcher auth
- Cloudflare R2: S3-compatible object store

**Scope:**
1. **Supabase Auth:** Researcher UI identity. Next.js SSR/cookie flow. FastAPI validates Supabase JWTs server-side. Browser never directly mutates scientific DB
2. **Database connections:** Separate runtime/migration configuration. Supabase direct Postgres where supported, otherwise pooler session mode. Do not use transaction-mode pooler for SQLAlchemy workers
3. **R2:** Reuse S3ObjectStore. Configure endpoint, bucket, access key, secret. Bucket private. Least-privilege credentials
4. **Railway:** Service/deployment config per process. API listens on Railway PORT. Workers are private/background. Ingest worker gets persistent scratch volume for gdc-client cache only. Ingest image includes official gdc-client
5. **Vercel:** Monorepo root `apps/web`. Only public env values (API origin, Supabase URL/publishable key). No DB/R2/TypeSafe/research secrets on browser
6. **CORS/CSRF/Security:** Allow only configured web origins. Secure cookies, JWT validation. Security headers
7. **Secrets:** Document exact secret matrix by service
8. **Migrations:** Only one process runs schema upgrades. App replicas must not race
9. **Health/readiness:** API liveness + DB + object-store readiness. Workers startup diagnostics, structured heartbeat/metrics
10. **Environment separation:** local, test, staging, production. Preview web deployments must not target production write APIs

**Domain/API/models:** Add Supabase auth integration. No scientific schema changes.

**Tests:**
- Auth integration tests
- Environment isolation
- Secret matrix verification

**Acceptance:** Deployable to staging/production architecture. Auth working. Environment separation enforced. Secret matrix documented.

---

#### CJ-38: Observability, recovery, staging acceptance, release gate

**Mission:** Prove the final CancerJev implementation works in the actual deployment environment and make operational failure diagnosable/recoverable.

**Why now:** Last PR — the product must work end-to-end in production.

**Scope:**
1. **Observability:**
   - Structured correlation IDs across web/API/job/analysis/discovery/WorkUnit
   - Instrument API latency/errors, queue age, job duration/retries, worker lease loss, GDC API errors, gdc-client transfer bytes/failures, R2 latency/errors, DB connection/pool, Jev latency/errors/model, research-model latency/errors, token/usage budgets
   - OpenTelemetry and/or Sentry-compatible instrumentation without leaking scientific payloads or secrets
2. **Backup/recovery:**
   - Supabase backup/PITR strategy
   - R2 object-retention expectations
   - Recovery sequence, migration rollback/forward strategy
   - Test recovery of metadata references against existing R2 objects
3. **Staging smoke:**
   - Web login → API → Supabase DB → R2 → worker job → test deterministic fixture → Jev provider connectivity → research-provider connectivity
4. **Bounded live GDC:** Execute CJ-12 bounded open TCGA-LUAD workflow in staging
5. **Complete reasoning loop:**
   - Real bounded open GDC → Materialization → deterministic SearchRun → Candidate → Jev discovery → deterministic expansion → Finding → reproduction → literature retrieval → native research agent → Claims → deterministic validation → Jev semantic verification → Evidence Graph → locked deterministic follow-up
   - Produce machine-readable release receipt
6. **Failure injection:**
   - TypeSafe unavailable, research provider unavailable, R2 transient error, DB reconnect, worker death during lease, gdc-client interrupted/resumed, browser/API auth expiry
   - No failure may fabricate success/evidence
7. **Security release check:** Production browser/external-agent payloads contain no DB URL, Supabase service key, R2 secret, TypeSafe key, research-model key, controlled GDC credential, raw matrix
8. **Load smoke:** Bounded concurrent API reads, job claims, Jev tasks
9. **Final documentation:**
   - Local runbook, staging runbook, production deployment, incident recovery
   - Scientific reproducibility guide
   - Jev question-set/calibration guide
   - External-agent guide
   - Update README status

**Acceptance:** Local and cloud-staging acceptance receipts reproducible and documented. Complete reasoning loop proven. Failure injection cannot fabricate success.

---

## 2. Dependency Diagram

```
CJ-09 (Packaging/CI)
  └── CJ-10 (Identity freeze)
  │     └── CJ-11 (Job fencing)
  │           └── CJ-12 (GDC acquisition)
  │                 └── CJ-13 (Artifact-backed analysis)
  │                       ├── CJ-14 (Descriptive engines)
  │                       │     └── CJ-16 (SearchRun/CandidateObservation)
  │                       │           ├── CJ-17 (JevService)
  │                       │           │     └── CJ-18 (CandidateState+Jev modes)
  │                       │           │           └── CJ-19 (Adaptive search)
  │                       │           │                 └── CJ-20 (Finding+reproduction)
  │                       │           │                       └── CJ-21 (Research contracts)
  │                       │           │                             ├── CJ-22 (Native agent)
  │                       │           │                             │     └── CJ-23 (Submission verifier)
  │                       │           │                             │           └── CJ-24 (Evidence graph)
  │                       │           │                             │                 ├── CJ-25 (Synthesis)
  │                       │           │                             │                 │     ├── CJ-26 (HypothesisLock+status)
  │                       │           │                             │                 │     │     └── CJ-27 (Native E2E)
  │                       │           │                             │                 │     │           ├── CJ-28 (Literature)
  │                       │           │                             │                 │     │           ├── CJ-29 (Cockpit UI)
  │                       │           │                             │                 │     │           └── CJ-30 (Handoff)
  │                       │           │                             │                 │     │                 └── CJ-31 (External API)
  │                       │           │                             │                 │     │                       ├── CJ-32 (Scheduler)
  │                       │           │                             │                 │     │                       ├── CJ-33 (Modes)
  │                       │           │                             │                 │     │                       ├── CJ-34 (Benchmarks)
  │                       │           │                             │                 │     │                       ├── CJ-35 (Convergence)
  │                       │           │                             │                 │     │                       └── CJ-36 (BYO)
  │                       │           │                             │                 │     │                             └── CJ-37 (Production)
  │                       │           │                             │                 │     │                                   └── CJ-38 (Release)
  └── CJ-15 (Partition) ──┘           │                             │                 │     │
                                      └─────────────────────────────┘                 │     │
                                                                                      └─────┘
```

## 3. Summary by Priority

### MUST FIX BEFORE SCIENTIFIC CLAIMS (HIGH)
- CJ-10: Identity/metadata freeze — hash doesn't capture sample type
- CJ-11: Job fencing — exhausted attempts stuck permanently
- CJ-13: Artifact-backed execution — current legacy path accepts caller rows
- CJ-15: Validation firewall — currently no partition separation

### SHOULD FIX BEFORE V1
- CJ-09: Packaging/CI — scientific not in wheel, no frontend CI
- CJ-12: GDC acquisition — no production acquisition flow
- CJ-14: Descriptive engines — empty placeholders
- CJ-16: SearchRun/CandidateObservation — core deterministic search
- CJ-17: JevService — needed for semantic triage
- CJ-20: Finding immutability + reproduction
- CJ-21–CJ-27: Native research loop E2E

### CAN DEFER
- CJ-28–CJ-30: Literature, cockpit, handoff
- CJ-31–CJ-36: External agent network
- CJ-37–CJ-38: Production deployment / observability

## 4. Key Architecture Principles Preserved

1. **Code measures** — deterministic scientific code authoritative for factual computation
2. **Jev judges** — Jev estimates narrow semantic properties of frozen structured state only
3. **Agents reason** — generative models propose mechanisms, alternatives, predictions, falsifiers, experiments
4. **Evidence decides** — scientific status advances only through actual evidence and deterministic policy
5. **Four ledgers never collapse** — Scientific, Semantic, Reasoning, Synthesis remain separate
6. **Native first** — same contracts for native and external agents
7. **No AI consensus = evidence** — agent convergence is scheduling metadata only
8. **No arbitrary code execution** — server-side allowlisted ResearchActions only
9. **Reproducibility** — Finding reproducible from snapshot + IDs without live GDC or Jev
10. **Discovery/validation separation** — reserved before discovery, locked before access