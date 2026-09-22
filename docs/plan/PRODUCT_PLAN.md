# CancerJev Product Plan

## Mission

CancerJev searches public cancer data for reproducible observations, proposes
competing explanations, selects discriminating tests, and records exactly what is
known, unknown, unavailable, and not examined. It is a research system, not a
diagnostic or treatment system.

Deterministic code owns scientific truth: it performs the broad registered search,
applies multiple-testing correction, QC, coverage, and eligibility gates, and decides
candidate eligibility. Jev owns bounded semantic judgment over the compact candidate
shortlist. Research agents own proposals. Versioned CancerJev policy connects these
authorities without allowing one to impersonate another.

## Absolute data promise

CancerJev uses only freely and anonymously available public data. Every GDC file must
explicitly state `access=open`. Missing, unknown, restricted, and controlled access
fail closed. CancerJev never accepts or transmits GDC credentials.

Acquisition always chooses the first scientifically adequate option:

```text
metadata
  -> minimal processed open file
  -> bounded open BAM slice
  -> bounded public-file transfer
```

V1 prohibits full BAM downloads and unbounded slicing. A slice supports conclusions
only inside its registered genes or closed coordinate ranges.

## Product layers

1. **Public data foundation:** frozen source identity, minimal acquisition,
   canonical materialization, and coverage.
2. **Deterministic discovery:** versioned registered engines and searches, complete
   result artifacts, tested universes, method-specific deterministic candidate gates,
   Findings, and reproduction.
3. **Semantic judgment:** TypeSafe-backed JevService over compact CandidateState.
4. **Native research loop:** Claims, evidence, ResearchState, actions, validation,
   and replication.
5. **Researcher and network utility:** cockpit, handoff, optional benchmarked
   distributed contributors, and production operations.

V1 discovery is deliberately small: mutation recurrence, mutation relationships, copy
number, RNA description, defined-group expression comparison, CNV/RNA and mutation/RNA
association, cohort/subtype comparison, and survival association (families D01–D09).
The authoritative scope and per-method contracts live in the
[V1 discovery catalogue](../scientific/discovery-catalogue-v1.md); pathway analysis,
clustering-based subtyping, and advanced modalities are explicitly deferred and are
not V1 scope.

## Milestones

### Gate 0 — Implementation readiness

CJ-R00 repairs verified baseline defects, establishes noninteractive CI, completes
packaging, connects artifact execution, strengthens identities and fencing, removes
unsafe full-file acquisition behavior, and proves the repository is a stable starting
point. Nothing in R01–R33 starts before this gate passes.

### Milestone A — Trusted scientific foundation

CJ-R01–R08 deliver reproducible builds, complete open snapshots, recoverable jobs,
minimal acquisition, artifact-only execution, runtime isolation with project
boundaries and quotas, a hidden
public validation partition, and trusted public mutation/CNV/RNA summaries.

Exit: one public dataset can be acquired minimally, frozen, materialized, partitioned,
and analyzed without caller-controlled scientific values or ambiguous coverage.

### Milestone B — Deterministic discovery and Jev

CJ-R09–R15 add defined cross-modal/group and survival engines, immutable Findings and
reproduction, SearchRun over registered methods with complete result artifacts and
method-specific deterministic candidate gates, CandidateObservation/CandidateState,
one JevService and Semantic Ledger, batched typed Jev questions, and bounded
policy-driven follow-up.

Exit: broad deterministic discovery produces reproducible SearchRuns and
deterministically gated candidates; Jev semantically triages the compact shortlist;
registered follow-up expands only within explicit public-data and cost budgets.

### Milestone C — Native closed-loop CancerJev

CJ-R16–R25 add identifiers, Claims, evidence, shared work contracts, verified public
literature, submission validation, a native agent, Evidence Graph, ResearchState,
ResearchAction, hypothesis locking, validation, and complete native acceptance.

Exit: the application can complete one auditable research loop without external
agents and without letting model output become scientific fact.

### Milestone D — Researcher utility

CJ-R26–R27 consolidate and harden the incremental research surfaces built during
R05–R25 into the complete researcher cockpit, then deliver exact handoff/review
packages. Thin functional screens already exist at R05, R08–R10, R12–R15, and R24;
R26 is polish, coverage, accessibility, and workflow coherence rather than the first
usable interface.

Exit: a researcher can understand, reproduce, export, review, and continue a result
without reading database rows or logs.

### Milestone E — Distributed network (optional)

CJ-R28–R32 add hidden benchmarks, capability profiles, replicated scheduling,
disabled-by-default external contributions, convergence policy, and adversarial/load
acceptance. This milestone is an optional later program: native CancerJev can reach
production release (Milestone F) without it.

Exit: bounded public EvidencePackets can be distributed without widening data access
or scientific authority.

### Milestone F — Production release

CJ-R33 supplies deployment, monitoring, recovery, backup/restore, release evidence,
and rollback. On the native path it may follow Milestone D directly; a
distributed-enabled deployment additionally requires the Milestone E acceptance
evidence.

Exit: live acceptance proves public-only minimal acquisition, no GDC credentials,
reproducible science, recoverable operations, and a complete native user journey.

## Product completion rule

Milestones are gates, not themes. A partial test suite, present class, queued job, or
rendered screen is not completion. Each CJ must meet its individual acceptance file,
the milestone exit, relevant regression suites, and current architecture rules.
