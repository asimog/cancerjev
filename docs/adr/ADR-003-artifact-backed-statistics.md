# ADR-003: artifact-backed deterministic statistics and V1 Findings

Status: accepted; approved by the user before implementation.
Branch: `codex/pr09-deterministic-statistics`, based on main after merged PR #8.

## Problem, current architecture, and classification

This is a Large change: production worker contracts, scientific policies, Finding
contracts, shared job lifecycle, and persisted execution context change.

Verified current owners and gaps:

- PR #8 owns immutable materialization/source lineage, canonical v2 records, parser
  policies, verified object staging, and frozen snapshot identity. Reuse those layers.
- `DurableResourceService.create_analysis` already persists an Analysis and queues
  `run_analysis_from_artifacts` with only analysis_id. It currently checks artifact
  existence, not scientific lineage or engine parameters.
- `workers/statistics` instead claims legacy `run_analysis` and `reproduce_finding`,
  and accepts caller rows, cohort size, and input hashes. Remove these production paths.
- `packages/statistics` owns numerical primitives, including one BH implementation.
  `scientific/crossmodal` duplicates assembly and silently overwrites duplicate keys.
  `scientific/survival` provides only a median estimate. `scientific` is not included
  in the current wheel package list; production code must live in packaged modules.
- Resource service/repositories own Analysis/Finding persistence. `persist_finding`
  currently requires an already completed Analysis, creating a split completion boundary.
- `workers/runtime` owns lease/heartbeat and separate job success/failure transactions.
  Scientific completion must use the same lease-checked transaction as job success.

## Proposed interface assembly and ownership

```text
POST /v1/analyses -> strict engine parameters + persisted Analysis/Cohort
  -> run_analysis_from_artifacts {analysis_id}
  -> lease-aware AnalysisExecutionService
  -> frozen execution manifest + registered lineage verification
  -> immutable object verification + canonical schema validation
  -> shared biological alignment and eligibility/QC
  -> deterministic engine registry
  -> typed Findings
  -> one transaction: Findings + Analysis completed + audit + Job succeeded
```

Add `AnalysisExecutionService` under `packages/resources`. It owns resolution and
execution orchestration; it does not own statistical formulas or storage implementation.
Keep registry, alignment, endpoints, and scientific implementations in coherent modules
under `packages/statistics`. Canonical result contracts stay in `packages/schemas`.
SQL lookup and locking remain in database repositories and the existing queue boundary.
No new service, persistence database, object abstraction, or dependency is planned.

Expose narrow reusable public operations for PR #8 verified artifact/snapshot reads
instead of invoking MaterializationService private methods or copying their logic.
Preserve ingest behavior when extending shared runtime lifecycle operations.

## Artifact resolution and execution manifest

Resolve Analysis, its linked Job, Cohort, and Snapshot from durable resources. Validate
cohort membership and case/sample relationships against frozen identity, not caller N.
Validate the registry engine/version and strict parameter model before scientific reads.

Freeze selected materialization IDs, source binding IDs, object hashes, logical hashes,
parser/schema/policy versions, cohort content hash, and normalized parameters in a
server-generated execution manifest before calculation. Add migration 0004 for persisted
manifest/failure metadata where required; never change 0001..0003.

Select required modalities and explicit RNA measurement from supported PR #8 lineage.
Allow explicit materialization ID selection only after full lineage checks. Otherwise
resolve the unique supported set; competing versions for the same scientific source
must fail rather than choose by timestamp. Deduplicate the same physical input reference.
Expected input hashes are assertions against resolved lineage, never authority to bypass it.
Missing modality or requested measurement, wrong snapshot, unsupported parser/schema/policy,
missing/corrupt bytes, and unknown engines fail closed.

Verify staged physical SHA-256, declared row counts, canonical records and recomputed
PR #8 logical hashes. Preserve original order for input hash verification, then use
stable scientific ordering. Filter/projection through existing Arrow/DuckDB capabilities
keeps molecular loading bounded; enforce documented resource and hypothesis limits.
Findings may reference a registered eligibility artifact when exact membership exceeds
the existing metadata payload limit; do not silently truncate or raise the global limit.

## Canonical biological alignment and duplicates

One alignment layer owns observation identity, membership, coverage, duplicates,
missingness, and group construction. Return exact eligible/excluded/missing IDs, total
and eligible N, per-modality and joint coverage, and policy versions.

Sample engines join exact frozen case/sample/gene identities; aliquots remain provenance
and are never equated across assays. Multiple assay aliquots for one measurement are
ambiguous unless an explicit supported reduction applies. No case-only cross-sample join.
Inferential sample engines reject repeated observations from the same case rather than
treat correlated samples as independent. Descriptive sample results disclose that QC.

`duplicate-observations-v1`: collapse exact canonical duplicate observations, recording
their counts. Mutation counts additionally deduplicate biological variants by selected
observation + chromosome/coordinates/ref/alt; gene presence is a versioned binary union.
Distinct variants remain distinct. Conflicting RNA/CNV values for one observation/gene
fail instead of overwriting or averaging. Conflicting clinical endpoints exclude that
case with an explicit reason. Results must not depend on source order or artifact order.

Mutation eligibility comes from verified complete supported callsets and frozen source
coverage, including valid zero-row callsets. Absence of mutation rows alone is not
coverage. Reject callsets with rejected rows for negative-state inference. Recurrence
describes the supplied masked somatic calls, not proof of biological wild type or drivers.
Case-level mutation presence unions calls across the explicitly selected primary samples;
require complete selected-sample callset coverage for case-level negative classification.

## Strict engine registry and V1 methods

Each definition includes canonical name/version, strict parameters, required modalities,
supported parser/schema/policy versions, observation unit, minimum N, and typed results.
All RNA engines require an explicit one-of-six PR #8 measurement label; never auto-select.
Non-estimable tests emit typed QC/status results without invented effect, p, or q.

| Engine v1 | Observation and proposed baseline |
| --- | --- |
| `mutation_frequency` | Case; masked-callset recurrence, Wilson binomial interval, exact eligible/mutated membership |
| `eligible_somatic_mutation_count` | Sample; distinct eligible variants and recorded filtering; unnormalized count, never TMB |
| `mutation_cooccurrence` | Case; bounded explicit gene list (maximum 100), binary state, 2x2 table, two-sided Fisher exact test, odds ratio/direction with explicit zero-cell/non-estimable handling |
| `cnv_frequency` | Sample; gene-level ASCAT3 absolute copy number only; versioned caller-explicit amplification/deletion cutoffs, no ploidy-adjusted claim or segment substitution |
| `rna_outlier` | Sample; sample variance, median and modified MAD score, explicit threshold default 3.5; MAD=0/constant/tiny-N statuses, no epsilon |
| `mutation_rna` | Exact sample; mutation-defined groups, Welch mean difference with Welch-Satterthwaite t confidence interval, at least two per group |
| `cnv_rna` | Exact sample; Pearson correlation with Fisher-transform interval, at least four variable finite pairs |
| `survival` | Case; versioned source endpoint, Kaplan-Meier curves/intervals and log-rank for two explicit groups; no Cox in V1 |
| `cohort_comparison` | Sample; expression comparison between two explicit persisted disjoint cohorts from the same snapshot, shared Welch primitive |
| `confounder_check` | Case/group; age, stage, missingness, modality coverage, selection and group-size imbalance indicators; no adjusted causal claim |

Bound tested genes/pairs through strict parameters. Persist gene/pair selections and
group definitions, including compared cohort IDs and membership hashes. Comparison groups
must be disjoint at the independent biological unit. No generic subgroup mining.
CNV numeric thresholds must be supplied and validated (deletion < amplification);
the transformation version and source measurement semantics accompany every result.
Categorical CNV input is rejected until a supported parser defines its categories.

## Survival endpoint and correction semantics

`gdc-overall-survival-v1`: Dead requires finite nonnegative days_to_death and is an event;
Alive requires finite nonnegative days_to_last_follow_up and is censored. Unknown vital
status, absent duration, contradictory data, and conflicting diagnosis-level endpoints
remain missing. Real source zero days may be retained; a missing time never becomes zero.
Do not silently substitute nested follow-up fields with a different time origin.

Report events/censoring, exact membership, curves and confidence intervals, and explicit
median-not-reached. Zero-event or undersized comparisons are non-estimable with QC, not
manufactured p-values or hazard ratios. Cox requires a later separately validated policy.

Use the existing tested BH implementation once per complete declared hypothesis family.
Family identity includes computation context and the deterministic hypothesis list.
Record planned/testable hypothesis counts, excluded hypotheses/reasons, correction
version and method. Only valid test p-values enter BH; non-estimable outputs have no q.
Frequency/outlier descriptive outputs do not receive fake significance values.

## Typed Findings and deterministic identity

Use a strict common envelope plus discriminated result types: frequency, count,
contingency, outlier/variance, group difference, correlation, survival, QC and
non-estimable result. Envelope includes snapshot/cohort/analysis, engine/version,
observation unit, eligibility, missingness/QC/confounders, parameters, input manifest,
measurement/endpoint/duplicate policies and correction family where applicable.

Compute a scientific result hash from canonical scientific context and results,
excluding clocks and random execution IDs. Derive persisted Finding ID deterministically
from analysis identity plus that result hash, preserving one Analysis owner per database
Finding while retries converge. Equal computations across Analyses share the scientific
result hash. Complete cross-environment reproduction remains PR #10.

Reuse the existing Finding table's indexed context and JSONB payload; add schema columns
only if needed for a concrete lookup. Do not require all Finding types to have a gene,
effect, p or q. Preserve explicit legacy data-version interpretation for existing records.

## Lease, lifecycle, and transaction behavior

Extend the existing runtime with transaction lifecycle hooks and a testable one-job path.
Start Job and transition its linked Analysis queued -> running together. Bind execution
to Job ID, worker ownership, and attempt; a forged analysis_id cannot target another Job.
Heartbeat remains independent during calculations.

On success, recheck ownership under the existing lease lock, validate the frozen execution
context, and call `complete_analysis` to persist all Findings and completion/audit together
with Job success. The result stored on Job contains compact Finding/resource IDs, not matrices.
Refactor completed-first Finding insertion so partial completion cannot escape a transaction.

On deterministic failure, mark Analysis and Job failed together with bounded structured
error/QC. For an explicitly retryable infrastructure failure, record the failed Analysis
attempt and queue the Job; allow failed -> running only through the linked retry operation.
Reclaimed jobs reuse the frozen manifest. An obsolete worker may never finalize after lease
loss. Exhausted expired attempts must produce terminal failure rather than stranded running
Analyses. Audit transitions and make finalization idempotent without duplicate Findings.

## Implementation order and verification

1. Strict registry/parameter contracts, typed Finding models and scientific golden tests.
2. Shared alignment/coverage/duplicate policy and versioned endpoint transformation.
3. Extend existing numerical primitives and implement all listed deterministic families.
4. Public verified artifact reader, execution resolution and persisted manifest (0004).
5. Resource completion/failure operations and lease-aware runtime/statistics integration.
6. End-to-end POST /v1/analyses -> real queue claim -> worker -> persisted Findings -> completion.
7. Regression tests for ingest, resources, lease expiry/retry/races, rollback and compatibility.
8. Ruff, full Python suite, real isolated PostgreSQL/migration tests, scientific golden tests,
   packaging check, complete diff review and current architecture/change documentation.
9. Open PR against main and check CI; do not merge.

Golden tests cover recurrence/counts/cooccurrence/exclusivity, CNV rules, outliers/MAD=0,
positive/null group differences, positive/constant correlations, cross-sample mismatches,
duplicates/reordering, measurement mismatch, endpoint precedence/missingness, survival
separation/zero events, cohort comparisons, confounder flags, whole-family BH and stable IDs.
Integration tests reject forged lineage/hashes/raw jobs, wrong snapshots/versions, missing
artifacts, invalid memberships, partial completion, lease loss and duplicate retry results.
Reuse PR #8 real materialization fixtures and clearly label deterministic synthetic science data.

Definition of done: all requested families and durable flow exist, required verification
actually runs with failures disclosed, scientific limitations are documented, and PR is open.
At proposal time no production code has changed and no PR #9 tests have been executed.

## Alternatives, risks, and confidence

Rejected raw scientific payloads, per-engine sample joins, silent duplicate overwrite,
first-match materialization selection, a parallel Finding database, arbitrary dynamic
engine imports, uncontrolled pairwise mining, and an unvalidated Cox model.

Main risks are mutation-negative eligibility, multiple samples per case, incomplete callsets,
clinical time-origin ambiguity, duplicate/conflicting assays, degenerate statistics, family
definition, metadata size, and stale-worker publication. These require explicit versioned
policies and targeted golden/integration tests rather than implicit defaults.

Architecture confidence: 8/10. Existing resource, storage and numerical dependencies fit
this direction. Confidence is limited by lifecycle changes across workers and the need to
validate scientific edge cases and resource bounds before implementation is complete.

Primary method references:
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pearsonr.html
- https://lifelines.readthedocs.io/en/latest/fitters/univariate/KaplanMeierFitter.html
- https://lifelines.readthedocs.io/en/latest/lifelines.statistics.html
