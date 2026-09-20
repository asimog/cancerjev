# CancerJev Architecture

This is the canonical architecture and its implementation boundary. The three
computational authorities describe the intended product; only the deterministic
foundation is implemented today. Requirements below for absent resources are
planned contracts, not claims of deployed behavior.

## Current implementation map

| Owner | Implemented responsibility and authoritative state |
| --- | --- |
| `packages/gdc` | Official GDC open-access policy, bounded REST metadata, frozen identity, PR #8 parsers and canonicalization |
| `packages/schemas` | Snapshot, identity, molecular v2, resource and compact job contracts |
| `packages/resources` | Snapshot registration, verified frozen-graph reads, cohort validation, source/materialization lineage, analysis request validation |
| `packages/database` | PostgreSQL metadata, immutable resource records, audit events, durable jobs and leases |
| `packages/storage` | Verified File/S3 CAS bytes, atomic local snapshot publication and Parquet |
| `workers/ingest` | Compact materialization jobs using existing PR #8 parsers |
| `packages/statistics`, `scientific`, `workers/statistics` | Deterministic primitives and legacy inline analysis handler; durable artifact-based analysis execution is not connected |
| `apps/api`, `apps/web` | Resource API and initial project/snapshot UI; not a complete discovery product |

Services own transactions and call repositories/storage contracts. Parsers use
canonical schemas and the frozen identity graph; they do not use PostgreSQL or
storage vendor SDKs. `FrozenSnapshotReader` is the shared resource-level read
contract used by materialization, cohorts and manifest selection.

Snapshot creation captures official `/status` before and after `/files` discovery,
rejects changed status, and freezes the raw status, release and source-policy
version in snapshot/provenance artifacts and PostgreSQL snapshot provenance.
This detects release changes, not atomic upstream consistency. Required identity
fields cannot be removed by callers. Caller-provided release strings are rejected.
Every `/files` discovery ANDs caller filters with `files.access = open` and checks
returned access. Redirects, alternative production hosts and authentication
headers are rejected. `/files/versions`, `/history/{uuid}` and endpoint `_mapping`
are metadata inspection helpers; they do not authorize acquisition or update
existing snapshots.

`POST /v1/snapshots/{id}/manifest` resolves the published snapshot from registered,
verified immutable artifacts. IDs must be a nonempty allowed subset. The upstream
manifest must exactly match the frozen UUIDs, filenames, sizes, MD5s and an allowed
transfer state (`validated` or `released`). Cohort case/sample IDs and their parent relationships must belong to the
same graph. Analysis inputs must name existing materializations with matching
snapshot, modality and measurement. Output SHAs are derived from those records;
a registered SHA alone is never sufficient. These checks do not claim engine-
specific scientific validation or artifact-based execution, which remain planned.

Migration `0004` freezes analysis scientific inputs and snapshot artifact links.
Historical SHA-only analyses remain readable with empty materialization references;
no lineage is invented or silently backfilled. New API snapshot artifacts publish
to the configured CAS. Legacy snapshot-relative filesystem artifacts remain
readable where the original snapshot root is mounted.

The Jev, search/candidate, reproduction/replication and reasoning/evidence graph
stages below are planned. Existing Finding persistence and statistics primitives
do not implement that full pipeline. Jev transport was reverted in merged PR #3;
there is currently no production Jev implementation.


## 1. Architectural invariant

CancerJev defines three computational authorities with deliberately different
permissions. Deterministic Science is partially implemented; the other two are planned.

### Deterministic Science

Owns factual scientific computation.

Includes:

- GDC identity and access policy;
- source verification;
- cohort membership;
- sample/aliquot alignment;
- molecular values;
- statistics;
- FDR;
- confidence intervals;
- residuals;
- QC;
- replication;
- scientific status transitions.

### System One / Jev

Owns bounded semantic judgments over supplied immutable state.

Includes:

- semantic pattern characterization;
- relevance/reranking;
- follow-up-analysis relevance;
- retrieved-evidence gating;
- citation/claim relationship classification;
- semantic agent-output verification;
- candidate entity/hypothesis alignment.

Jev may propose semantic signals.

CancerJev policy decides what action those signals cause.

### Generative Research

Owns open-ended proposals.

Includes:

- mechanisms;
- alternative hypotheses;
- literature synthesis;
- predictions;
- falsifiers;
- experiment proposals.

Generative output is untrusted reasoning until validated.

## 2. Canonical pipeline (target architecture)

    NCI GDC
       │
       ▼
    DatasetSnapshot
       │
       ▼
    SourceArtifact
       │
       ▼
    Materialization
       │
       ▼
    Cohort + biological alignment
       │
       ▼
    AnalysisRun / SearchRun
       │
       ▼
    CandidateObservation
       │
       ▼
    deterministic candidate gate
       │
       ▼
    CandidateState
       │
       ▼
    JevEvaluation
       │
       ▼
    versioned CancerJev policy
       │
       ├── archive
       ├── hold
       └── ExpansionRecipe
               │
               ▼
          deterministic computation
               │
               ▼
          updated CandidateState
               │
               ▼
             Finding
               │
               ▼
          ReproductionRun
               │
               ▼
             Block
               │
               ▼
            WorkUnit
               │
               ▼
             Agent
               │
               ▼
           Submission
               │
               ▼
             Claims
               │
       ┌───────┴─────────┐
       ▼                 ▼
    deterministic       Jev
    verification      semantic
       │             verification
       └───────┬─────────┘
               ▼
             Evidence
               │
               ▼
          EvidenceRelation
               │
               ▼
          Evidence Graph
               │
               ▼
        deterministic follow-up
               │
               └───────────────→ new scientific evidence

## 3. Data authority

GDC REST is authoritative for upstream released-data identity.

CancerJev's frozen snapshot/materialization is authoritative for reproduction.

Live GDC responses must never silently replace the inputs of an existing
Analysis/Finding.

Every molecular V1 source must be explicitly open access.

Controlled data and authentication tokens are rejected.

## 4. Scientific resources (implemented and planned)

DatasetSnapshot, DatasetObject, MaterializationSource, Materialization, Cohort,
Analysis metadata and Finding persistence exist. Other named resources below are
planned. SourceArtifact is the conceptual source stage, currently represented by
DatasetObject plus MaterializationSource. AnalysisRun maps to current Analysis
metadata; its artifact worker remains planned.

Core scientific resources:

    DatasetSnapshot
    DatasetObject
    MaterializationSource
    Materialization
    Cohort
    AnalysisRun
    SearchRun
    CandidateObservation
    Finding
    ReproductionRun
    ReplicationAttempt

Core semantic resources:

    CandidateState
    JevQuestionSet
    JevEvaluation
    JevPolicy

Core reasoning resources:

    Block
    WorkUnit
    Agent
    Submission
    Hypothesis
    Claim
    Prediction
    Falsifier
    ExperimentProposal

Evidence resources:

    Evidence
    EvidenceRelation
    EvidenceGraphGeneration
    HypothesisLock
    ScientificStatusTransition

## 5. Jev integration rules (planned)

When implemented, exactly one production TypeSafe transport implementation is required.

All domain services call CancerJev's `JevService`, not the SDK directly.

Use the official asynchronous TypeSafe Python client when implementing this stage;
SDK compatibility must be verified then. No Jev dependency is added by this PR.

A Jev request binds:

    state schema version
    state hash
    question-set ID/version
    concrete model/version
    policy version

Question primitives:

- Noul: independent binary semantic proposition;
- Choice: genuinely mutually exclusive semantic alternatives;
- Score: ordered qualitative rubric only.

Never use Jev for arithmetic, FDR, counts, dates, numeric normalization or
scientific measurement.

Never assume two different primitives asking similar questions will satisfy a
mathematical consistency relation.

Independent questions sharing one state should be sent together.

Dependent questions require a subsequent state/request.

## 6. Progressive disclosure (planned)

Do not expose the entire search space to Jev.

Use:

    vectorized deterministic scan
      → hard deterministic reduction
      → compact semantic state
      → Jev
      → richer deterministic/context retrieval for survivors
      → Jev if needed

For retrieval:

    lexical/embedding/metadata search
      → shortlist
      → Jev rerank/gate
      → source verification
      → agent context

For entity alignment:

    cheap deterministic candidate pairs
      → Jev semantic alignment
      → policy/human resolution

Never perform all-pairs semantic comparisons when a cheap candidate generator
can reduce the space first.

## 7. Three ledgers (target boundaries)

Scientific Ledger:
real observations and deterministic scientific transformations.

Semantic Ledger:
immutable JevEvaluation records.

Reasoning Ledger:
agent hypotheses, Claims and proposals.

Cross-ledger references are explicit.

No ledger silently mutates another.

## 8. Scientific hashing

Scientific result identity contains deterministic inputs and results only.

It excludes:

- Jev output;
- agent output;
- scheduler priority;
- timestamps;
- worker host;
- user-interface state.

Semantic evaluation identity independently includes its state, question set,
model and full answer distribution.

## 9. Queue model

PostgreSQL jobs remain V1's durable queue.

Workers claim with `FOR UPDATE SKIP LOCKED` and renewable leases.

New resource jobs contain durable IDs, not molecular matrices. The existing legacy
statistics handler still expects inline rows and does not consume the queued
`run_analysis_from_artifacts` jobs. Connecting it is a separate implementation.

Workers resolve objects from PostgreSQL + shared object storage.

## 10. Storage

Current stores hold scientific metadata, source/Parquet objects and audits. Ledger,
graph, evidence-packet and receipt uses below describe planned extensions.

PostgreSQL:
metadata, states, queues, ledgers, graph metadata and audits.

S3-compatible CAS:
source files, Parquet, evidence packets and receipts.

Parquet/DuckDB/Polars:
omics-scale analytics.

## 11. Deployment

Implemented local data plane (research/validation workers remain placeholders):

    Docker Compose
      Postgres
      MinIO
      API
      web
      ingest + statistics workers

Planned production deployment (not verified or provisioned by this repository):

    Vercel → Next.js
    Railway → API + persistent workers
    Supabase → PostgreSQL + researcher Auth
    Cloudflare R2 → shared immutable S3-compatible CAS

No Redis/Kafka/Kubernetes is required for V1.

## 12. Security boundary (requirements)

Browsers never receive provider secrets.

External agents never receive infrastructure credentials.

The server never executes external agent code.

Retrieved literature/web content is untrusted data.

Provider failure produces pending/held work, never fabricated semantic output.

## 13. Scientific status (planned evidence criteria)

Scientific-state changes depend on deterministic evidence criteria.

Examples:

    discovery observation
    internal holdout support
    independent dataset replication
    functional support
    mechanistic support

Jev may annotate relevance or relationship.

It cannot perform the status transition by itself.

## Implementation references

- [Durable resource contracts](docs/architecture/resources.md)
- [PR #8 materialization contracts and limitations](docs/architecture/gdc-materialization.md)
- [GDC trust, frozen resources and storage decision](docs/adr/ADR-003-gdc-trust-and-shared-storage.md)
- [PR09 change and verification record](docs/changes/pr09-architecture-gdc-hardening.md)

Older design documents under `docs/architecture` are historical elaborations;
this document governs current architectural claims where they differ.
