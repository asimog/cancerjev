# CancerJev V1 Discovery Catalogue

Status: documentation only. This catalogue defines **what CancerJev V1 searches for**
and the minimum scientific contract of each discovery family. It authorizes no
implementation, adds no runtime component, and does not create a registry: discovery
methods are ordinary registered scientific engines under the CJ-R05 Engine Registry.
CJ-R08–CJ-R12 are the implementation milestones; the
[canonical roadmap](../plan/IMPLEMENTATION_ROADMAP.md) remains authoritative for order
and acceptance.

## 1. Discovery pipeline

```text
Public GDC
  -> frozen snapshot
  -> minimal acquisition (metadata, minimal processed file, bounded BAM slice)
  -> canonical mutation / CNV / RNA / public clinical artifacts
  -> registered deterministic scientific engine
  -> SearchRun against a frozen cohort and tested universe
  -> complete deterministic result set (all tested units)
  -> multiple-testing correction where applicable
  -> QC / coverage / eligibility checks
  -> method-specific deterministic candidate gate
  -> CandidateObservation
  -> related deterministic evidence combined where appropriate
  -> CandidateState
  -> TypeSafe Jev (batched atomic typed questions)
  -> versioned CancerJev routing policy
  -> registered bounded follow-up
       |- further deterministic analysis
       |- cross-cohort analysis
       |- public literature
       `- bounded BAM slice / read-level analysis
  -> Claims / Evidence / ResearchState
  -> later generative research reasoning (CJ-R20)
  -> competing hypotheses / predictions / falsifiers
  -> registered deterministic test
  -> HypothesisLock
  -> hidden validation
```

Authority rules that hold across every family:

- Deterministic code owns eligibility, tested universes, measurements, statistics,
  effects, intervals, p/q values, correction, QC, missingness, coverage, candidate
  eligibility, Finding identity, reproduction, and validation outcomes.
- Jev judges only a compact CandidateState assembled from already-gated candidates.
  Jev never sees complete SearchRun result tables, raw matrices, or raw BAM.
- Generative LLMs propose mechanisms, competing hypotheses, predictions, falsifiers,
  experiments, literature needs, and next actions — never statistics, candidate gates,
  or tested-universe definitions.
- `missing != negative`, `unavailable != negative`, `not examined != negative`, and
  `bounded regional evidence != whole-assay evidence` in every family below.

## 2. Registration and SearchRun

- The CJ-R05 Engine Registry is the single registered scientific-engine mechanism. A
  discovery method registers there with supported inputs, compatible schemas,
  parameters, coverage requirements, output contract, and method version.
- A SearchRun (CJ-R12) means: run this exact registered method/version over this exact
  frozen cohort and tested universe. It records snapshot/cohort identity, input
  artifact identities, engine/method/version, parameters, purpose, planned/tested/
  excluded universes with exclusion reasons, multiple-testing family, correction
  method, coverage, status, result artifact identity, candidate count, and scientific
  identity/hash where appropriate.
- Complete result tables (for example one row per tested gene) remain immutable
  Parquet/CAS artifacts. PostgreSQL holds compact SearchRun metadata and bounded
  CandidateObservations only. Full result tables never enter job JSON and are never
  sent to Jev.

## 3. Minimum method contract

Every implemented method/version specifies only what is necessary:

1. scientific question;
2. required inputs;
3. eligible population;
4. tested universe;
5. exclusions and exclusion reasons;
6. missing-data policy;
7. coverage requirements (complete assay vs bounded region);
8. statistical method;
9. effect/statistic;
10. interval where applicable;
11. p/q where applicable;
12. QC requirements;
13. candidate criteria;
14. method version;
15. output type.

Candidate rules are method-specific and deterministic. There is no universal rule such
as `q < 0.05 = interesting`. Scientific interest may depend on statistical
significance, effect magnitude, sample size, event count, group balance, QC,
missingness, coverage, and model diagnostics. The candidate gate always runs before a
result becomes a CandidateObservation; `CandidateObservation` means "this deterministic
result qualified under the registered scientific candidate policy", never "Jev liked
it".

## 4. Discovery families

### D01 — Mutation recurrence (primary CJ: R08)

Find recurrent somatic alterations within the frozen cohort: gene-level mutation
frequency and recurrent specific variants/hotspots.

Record: tested gene/variant universe, eligible cases, mutated cases, denominator,
frequency, missing/excluded cases, coverage, QC, method version. Missing mutation data
is never equated with wild type.

### D02 — Mutation relationships (primary CJ: R08)

Identify mutation pairs that occur together or avoid one another more than expected:
co-occurrence and mutual exclusion using explicit deterministic statistical methods.

Record: tested pair family, contingency counts, eligible N, effect, interval where
applicable, p, q, exclusions, missingness, coverage. R09 does not duplicate ordinary
mutation–mutation co-occurrence unless it performs a genuinely different
covariate-aware model.

### D03 — Copy-number discovery (primary CJ: R08)

Identify recurrent copy-number alterations: amplification frequency, deletion
frequency, and recurrent CNV segments/regions.

Record: tested universe, eligible samples, affected samples, denominators,
segment/gene identity, coverage, missing/excluded counts, QC, method version.

### D04 — RNA descriptive discovery (primary CJ: R08)

Describe RNA expression and detect unusual expression patterns: distributions, gene
variability, expression outliers.

Missing expression is never silently replaced with zero. Variable expression is not
automatically implied to be biologically meaningful.

### D05 — Differential expression / defined group comparison (primary CJ: R09)

Compare RNA expression between registered biological groups, for example KRAS mutant
vs wild type, amplified vs non-amplified, or subtype A vs subtype B.

Require explicitly: group definition, eligible population, normalization/method,
effect, interval where appropriate, p, q, tested gene family, QC, missingness,
coverage.

### D06 — CNV → RNA association (primary CJ: R09)

Determine whether copy number associates with RNA expression. The current `cnv_rna`
code is an implementation seed, not the intended whole discovery system. Support
scientifically registered variants such as same-gene CNV → RNA association first, and
later other specifically justified forms.

Recognize registered convergence (gene amplified + RNA elevated) and registered
discordance (gene amplified + RNA unexpectedly low, or no CNV + extreme RNA
overexpression). Discordance may generate a candidate only when it passes registered
deterministic rules. Jev never discovers discordance from raw matrices.

### D07 — Mutation → RNA association (primary CJ: R09)

Determine whether mutation-defined groups have associated expression differences, for
example mutation in X → altered expression of X, or mutation in X → registered
genome-wide expression differences. The tested universe must be explicit.

### D08 — Cohort / subtype enrichment and comparison (primary CJ: R09)

Determine whether a molecular feature differs between registered cancer cohorts or
public disease subtypes, for example enrichment in subtype A or differing alteration
frequency between cohorts. Do not combine biologically incompatible cohorts simply to
increase sample size.

### D09 — Molecular feature → survival (primary CJ: R10)

Test whether a registered molecular feature is associated with a versioned public
survival endpoint, preserving every current R10 requirement: endpoint definition, time
origin, censoring, eligibility, event minimums, ties, covariates, proportional-hazard
diagnostics where appropriate, multiplicity, and reporting. Broad discovery never
simplifies D09 into a generic survival-library call.

## 5. Multi-modal convergence (R12)

R12 deterministically recognizes when independent analyses implicate the same gene,
region, or biological entity — for example D03 recurrent amplification + D04 RNA
outlier + D06 strong CNV/RNA association + D09 survival association. Compatible
observations may combine into a stronger CandidateObservation/CandidateState.

The first version of convergence is deterministic and bounded orchestration over
compatible search observations. It is not a graph system and does not require Jev to
notice relationships across unrelated outputs. CJ-R21 later owns the richer Evidence
Graph.

## 6. Bounded read-level follow-up

BAM slicing exists so registered follow-up questions can be answered without
downloading large complete BAM collections. V1 documents two read-level categories;
CJ-R04 owns acquisition, deterministic engines own interpretation:

- **Local variant evidence:** usable local coverage, alternate-supporting reads,
  reference-supporting reads, and allele fraction where scientifically appropriate.
  Distinguish supported, not supported with adequate coverage, and insufficient
  coverage.
- **Regional read-depth evidence:** bounded local depth evidence against an appropriate
  comparison/reference with coverage and QC; report supports, contradicts, or
  inconclusive.

Outside the registered genes/closed regions, the state is `NOT_EXAMINED`, never
negative. Full BAM downloads, whole chromosomes, open-ended ranges, and unbounded
slicing remain prohibited. Breakpoint/fusion/splice engines are not V1.

## 7. Future / deferred

The following are explicitly deferred. They are recorded here so they are not
accidentally promoted into V1; implementing any of them requires a future CJ and
cannot be added by clarification:

- pathway enrichment;
- methylation integration;
- unsupervised molecular-subgroup discovery;
- single-cell RNA;
- fusion/splice analysis;
- structural-variant discovery;
- ATAC/chromatin data;
- spatial genomics;
- cfDNA;
- long-read analyses.

## 8. Non-goals

- No universal candidate threshold, no Jev-authored candidate rule, and no
  model-confidence substitution for deterministic evidence.
- No second registry (no separate SearchDefinition/DiscoveryMethod/CandidatePolicy
  registry): R05 registration plus this catalogue plus R12 SearchRun metadata express
  V1.
- No new storage, queue, graph, workflow, agent, or frontend framework.
- No database table merely because a concept appears in this document.