# CancerJev Architecture

This is the canonical architecture map after the CJ-R00 readiness gate and for the
CJ-R01–CJ-R33 implementation program. It separates current truth from target
architecture. Planned names are not claims that code exists.

## 1. Architectural status

Baseline: `2bf6c68d93741b9974f46983e0a35c691d69c1f1`.

| Boundary | Current owner | Current truth | Target CJ |
| --- | --- | --- | --- |
| Public GDC policy | `packages/gdc` | Official host, open-only filtering, terminal access denial, complete-BAM denial, transfer quarantine | R02, R04 |
| Frozen snapshots | `workers/ingest`, `packages/storage`, `packages/resources` | Published artifacts and complete normalized identity v2; legacy v1 remains readable | R02 |
| Materialization | `packages/gdc`, `packages/resources`, ingest worker | Public processed mutation/RNA/CNV/clinical parsers | R04, R08 |
| Durable resources | `packages/resources`, `packages/database` | Immutable scientific records, fenced job attempts, terminal recovery, and publication transactions | R01–R06 |
| Scientific execution | `packages/statistics`, `scientific`, statistics worker | Frozen-artifact `cnv_rna` path connected through server-owned Finding publication | R05, R08–R12 |
| Runtime isolation and quotas | none | No end-user login; runtime isolation and quotas are planned without user accounts | R00, R06 |
| Validation firewall | none | Not implemented | R07, R24–R25 |
| Jev | none | No SDK, adapter, service, or semantic ledger | R13–R15 |
| Research loop | none | No claims, evidence graph, state, actions, or native agent | R16–R25 |
| Researcher product | minimal `apps/web` | Project list and snapshot creation only; reproducible lint/build/browser gate | incremental checkpoints R05, R08–R10, R12–R15, R24; R26–R27 cockpit and handoff |
| Distributed network | none | External client is intentionally absent | R28–R32 |
| Production release | Compose development stack | No production release evidence | R33 |

CJ-R00 repaired the entry foundation without introducing the new product subsystems
assigned to later CJs.

## 2. HyperFlow boxes and ownership

CancerJev is one modular application. Each box owns one coherent responsibility and
communicates through application-owned contracts.

```text
Public Source Gateway
  -> Snapshot and Acquisition
  -> Canonical Materialization
  -> Deterministic Science
  -> Semantic Judgment (Jev)
  -> Native Research Loop
  -> Researcher Experience
  -> Optional Distributed Execution
```

### Public Source Gateway

Owner: `packages/gdc`.

Owns the official host allowlist, request bounds, response validation, explicit
`access=open` checks, retry classification, GDC schema mapping, and provider-specific
errors. It never owns CancerJev projects, Claims, Findings, or scientific status.

### Snapshot and Acquisition

Owners: `workers/ingest`, `packages/resources`, and `packages/storage`.

The snapshot owns frozen upstream identity and selection provenance. The acquisition
layer will own `OpenDataPolicy`, `AcquisitionPlan`, `BamSliceRequest`, and
`AcquisitionReceipt`. Storage owns immutable bytes; resource services own transaction
boundaries and lineage registration.

### Canonical Materialization

Owner: `packages/gdc` parsers behind resource/worker orchestration.

Transforms verified public source bytes into application-owned Parquet schemas and
diagnostics. Parsers do not access PostgreSQL, object-store SDKs, live GDC, Jev, or
user identity.

### Deterministic Science

Owners: `packages/statistics`, `scientific`, and an application execution service.

Owns eligibility, tested universes, measurements, estimators, confidence intervals,
multiple-testing correction, QC, scientific status, and immutable Finding identity.
Workers are replaceable execution adapters and may not redefine these rules.

Broad discovery is deterministic. Registered engines execute over frozen artifacts and
produce complete result artifacts; a method-specific deterministic candidate gate then
converts only qualifying results into CandidateObservations. V1 discovery families and
their minimum method contracts are defined once in the
[discovery catalogue](docs/scientific/discovery-catalogue-v1.md). Jev never selects,
rejects, or promotes search results.

### Semantic Judgment

Owner: the planned application-owned `JevService`; TypeSafe is an adapter.

Jev receives compact, typed CandidateState assembled from the gated candidate
shortlist. It never receives GDC credentials, raw BAMs, unrestricted matrices,
complete SearchRun result tables, or authority to change deterministic evidence.
Independent typed questions over one CandidateState are normally batched in one
request. Provider responses enter an append-only Semantic Ledger and are interpreted by
versioned CancerJev policy; no universal confidence threshold exists, and each action
is calibrated separately.

### Native Research Loop

Owners: planned Claims/Evidence, ResearchState, ResearchAction, and WorkUnit services.

The in-process native agent uses the same bounded contracts later exposed to remote
contributors. Native end-to-end acceptance is mandatory before external transport.

### Researcher Experience

Owners: `apps/api` for delivery contracts and `apps/web` for presentation.

The UI never owns scientific or access state. It displays authoritative labels and
cannot convert `not examined` or `unavailable` into `negative`.

Thin functional research surfaces appear alongside the scientific milestones that make
them meaningful: a minimal run view at R05, modality views at R08–R10, discovery views
at R12, Jev and follow-up views at R13–R15, and hypothesis-lock views at R24. R26
consolidates and hardens these into the complete researcher cockpit.

### Optional Distributed Execution

Owners: planned scheduler and contributor adapter.

Disabled by default until native acceptance, hidden benchmarks, capability profiles,
replication, quotas, abuse controls, and failure gates pass. Remote agents receive
bounded EvidencePackets, not database access or GDC authority.

## 3. Data ownership

| Data | Authoritative owner | Mutation rule |
| --- | --- | --- |
| GDC transport response | GDC adapter during bounded request | Ephemeral; map before crossing boundary |
| DatasetSnapshot identity | snapshot service | Publish once; supersede, never mutate |
| Source/materialized bytes | object store CAS | Content addressed and immutable |
| Resource metadata | PostgreSQL repositories through resource service | Transactional; invariants enforced in service and DB |
| Cohort definition | cohort resource | Immutable scientific membership |
| Analysis manifest | deterministic execution service | Frozen before execution |
| SearchRun and complete result artifact | discovery service; CAS bytes | Registered method/version over a frozen cohort; result artifact immutable |
| CandidateObservation | discovery service | Deterministic candidate-gate output; never created or edited by Jev |
| Finding | Finding service | Immutable; corrections supersede/retract |
| Semantic evaluation | Semantic Ledger | Append-only; never edits Finding truth |
| Claims/evidence | Evidence core | Versioned append/supersession semantics |
| ResearchState | synthesis service | Rebuilt from exact ledgers and evidence |
| UI projections | API/read models | Derived, never authoritative |

No independently owned module may update another module’s tables or private storage
layout directly.

## 4. Current implemented flow

```text
GDC /status + /files
  -> LogicalSnapshotService
  -> FileSnapshotRepository + File/S3 CAS registration
  -> DatasetSnapshot and SnapshotArtifact records
  -> verified MaterializationSource
  -> ingest materialization worker
  -> canonical Parquet + diagnostics + Materialization
  -> frozen Cohort
  -> Analysis + queued run_analysis_from_artifacts Job
  -> fenced statistics-worker attempt
  -> AnalysisExecutionService resolves and verifies frozen artifacts
  -> registered deterministic cnv_rna engine
  -> server-owned identity and immutable Finding publication
  -> Analysis and Job terminal success
```

Job payloads remain compact references. Molecular matrices do not enter queue JSON,
and workers do not own scientific identity or publication rules.

## 5. Target discovery and research flow

Broad discovery is deterministic. Jev enters only after a deterministic candidate gate
has produced a compact shortlist; generative reasoning enters only after evidence
exists.

```text
DatasetSnapshot
  -> AcquisitionPlan / AcquisitionReceipt
  -> AnalysisInputManifest
  -> registered deterministic search (SearchRun)
  -> complete deterministic result artifact (all tested units)
  -> multiple-testing correction + QC / coverage / eligibility checks
  -> method-specific deterministic candidate gate
  -> CandidateObservation
  -> deterministic combination of compatible observations
  -> CandidateState (compact derived evidence)
  -> JevEvaluation (batched atomic typed questions)
  -> versioned CancerJev routing policy
  -> bounded deterministic follow-up
       |- further deterministic analysis
       |- cross-cohort analysis
       |- public literature
       `- bounded BAM slice / read-level analysis
  -> immutable Finding
  -> reproduction
  -> Claims and Evidence
  -> ResearchState
  -> ResearchAction / WorkUnit
  -> native agent Submission (generative reasoning after evidence exists)
  -> competing hypotheses, predictions, falsifiers
  -> registered deterministic test
  -> HypothesisLock
  -> hidden validation / replication
  -> researcher handoff
```

- A `CandidateObservation` means the result passed the registered deterministic
  candidate policy. It never means "Jev liked this result."
- Complete SearchRun result sets stay in immutable artifacts; PostgreSQL holds compact
  SearchRun metadata and bounded CandidateObservations only.
- R12 deterministically connects compatible observations about the same gene, region,
  or entity; the richer Evidence Graph remains R21.
- Follow-up acquisition stays inside CJ-R04 bounds. A BAM slice supports only its
  registered variant/depth question; outside its regions the state is `NOT_EXAMINED`.
- Jev output is recorded as answer, probabilities, confidence, model/version, state
  hash, question-set version, usage, and errors; versioned policy, not a universal
  threshold, decides what follows.

Distributed scheduling is an optional adapter after this loop works natively.

## 6. Non-negotiable public-data boundary

- Only freely and anonymously available public data may be used.
- Every GDC file must explicitly declare `access=open`; missing, unknown,
  restricted, or controlled access fails closed.
- No GDC token, `X-Auth-Token`, GDC `Authorization`, cookie, token file, dbGaP
  credential, or transfer-tool token option may enter configuration, schemas,
  storage, logs, documentation, or requests.
- CancerJev does not require end-user login. Application/service credentials protect
  CancerJev resources only and never grant access to GDC data.
- Acquisition priority is fixed:

  ```text
  metadata
    -> minimal processed open file
    -> bounded open BAM slice
    -> bounded public-file transfer
  ```

- V1 prohibits full BAM downloads, whole-chromosome slices, open-ended ranges,
  unmapped-read requests, and unbounded slicing.
- Slice evidence is partial. Outside its registered genes/closed regions, the state
  is `NOT_EXAMINED`, never negative.
- Any authorization response is terminal `UNAVAILABLE_ACCESS`; no credential search
  or authenticated retry exists.

Changing this boundary requires replacement of the product mission and this
architecture, not an ordinary CJ.

## 7. Scientific identity and immutability

A scientific result identity must include frozen snapshot/cohort identity, exact
complete or partial input manifests, source hashes, coverage scope, examined universe,
engine/version/parameters, search or analysis identity, eligibility policy, correction
family/version, relevant runtime identity, and canonical deterministic output.

It excludes Jev answers, agent prose, scheduler state, UI state, and wall-clock noise.
Changing an identity-bearing field creates a new result. Findings are never edited
in place; correction uses supersession or retraction.

## 8. Four ledgers

1. **Scientific Ledger:** snapshots, manifests, analyses, Findings, reproduction,
   validation, and status transitions.
2. **Semantic Ledger:** CandidateState questions, model/SDK resolution, Jev answers,
   usage, errors, and routing decisions.
3. **Reasoning Ledger:** WorkUnits, agent inputs, submissions, critiques, budgets,
   and convergence decisions.
4. **Operational Ledger:** jobs, attempts, leases, retries, deployments, backups,
   incidents, and policy rejections.

Ledgers reference one another by stable identifiers. Semantic or reasoning events
cannot mutate the Scientific Ledger.

## 9. State distinctions

The system distinguishes public data available, public data not yet acquired,
examined positive/negative observations, region not examined, unavailable because
controlled, unavailable because no public source exists, and failed acquisition or
computation. These are never interchangeable; consensus cannot create evidence.

## 10. Dependency direction

```text
domain/scientific rules
  -> application-owned schemas and services
  -> database, storage, GDC, TypeSafe, and transport adapters
```

Scientific engines do not import vendor SDKs; parsers do not open database sessions;
UI does not mutate scientific tables; agents do not construct raw SQL; provider
response types do not leak into domain contracts.

## 11. Job and publication model

Jobs are durable PostgreSQL records with attempt history and per-claim attempt tokens
as fencing tokens, so stale workers cannot publish. Exhausted leases become terminal;
authorization failures are permanent. Scientific publication computes into
attempt-scoped outputs, verifies contracts/hashes, then transactionally publishes
metadata referencing immutable CAS bytes. Replay is idempotent.

## 12. Security and deployment

CJ-R06 introduces runtime isolation, project boundaries, service scopes, quotas, and
audit — without end-user accounts, passwords, sessions, or user roles. Until then,
the API is local-development only; CORS is not authorization. Logs contain stable IDs
and reason codes, not matrices, credentials, or raw provider
responses. Compose is a development topology. CJ-R33 owns production secrets,
backup/restore, observability, rollback, and release evidence for the native
system; the optional distributed program (CJ-R28–R32) never blocks native production
readiness and adds its own distributed-release acceptance when enabled.

## 13. Architecture change control

Create or supersede an ADR when a CJ changes data ownership, shared contracts,
persistence, external providers, dependency direction, or a critical invariant.
Each merged CJ updates this file and its roadmap status.

See the [canonical roadmap](docs/plan/IMPLEMENTATION_ROADMAP.md) and
[individual CJ specifications](docs/plan/cjs/README.md).
