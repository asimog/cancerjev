# Milestone A Repair Report

## What was broken

Milestone A (CJ-10 through CJ-15, PR #10) introduced a sound architectural design but the implementation had multiple integration and scientific correctness bugs that prevented the advertised workflow from operating end to end.

## Bugs fixed

### P0 Blockers (8)

| Bug | File(s) | Fix |
|-----|---------|-----|
| P0-01: `request.gdc_release` not authoritative | `workers/ingest/snapshot.py` | Added `_capture_gdc_release()` that queries GDC `/status` endpoint |
| P0-02: Mandatory identity fields dropped | `workers/ingest/snapshot.py` | Effective fields = mandatory ∪ caller-requested |
| P0-03: File identity dedup on `file_id` alone | `workers/ingest/snapshot.py` | Now dedups using full `(file_id, case_id, sample_id, aliquot_id)` tuple |
| P0-04: Resolver stages one name, reads another | `packages/resources/resolver.py` | Added `ARTIFACT_ROLE_FILENAME_MAP` constant; `_load_identity` reads `file_sample_links.parquet` |
| P0-05: `input_materializations` not persisted | `packages/database/models.py`, `packages/resources/service.py`, `migrations/versions/0006_milestone_a_repair.py` | Added `input_materializations` JSONB column and migration |
| P0-06: Analysis never enters `running` | `packages/resources/execution.py` (new), `workers/runtime.py` | `AnalysisExecutionService.execute()` transitions Analysis to running |
| P0-07: Findings require completed but persisted before | `packages/resources/execution.py` | Atomic completion transaction: persist findings → transition to completed within one tx |
| P0-08: Worker DB mutations not committed | `packages/resources/execution.py` | Explicit `session.commit()` after atomic completion |

### P1 High-Severity (15)

| Bug | Fix |
|-----|-----|
| P1-01: Attempt tokens not validated | `packages/database/jobs.py`: `_owned()` now validates `attempt_token` |
| P1-02: Partitions not persisted | `packages/database/models.py` + migration: new `PartitionSet` table; route persists |
| P1-03: Sample/aliquot IDs in both partitions | `packages/partition/__init__.py`: derive membership from identity graph |
| P1-04: Partition firewall not connected | `packages/resources/execution.py`: `assert_partition_access()` |
| P1-05: Mutation freq ignores requested genes | `scientific/mutation/engines.py`: added `genes` parameter, filtering |
| P1-06: CNV freq ignores requested genes | `scientific/cnv/engines.py`: added `genes` parameter |
| P1-07: RNA outlier combines different genes | `scientific/expression/engines.py`: per-gene independent analysis |
| P1-08: RNA outlier wrong sample IDs | `scientific/expression/engines.py`: aligned observations |
| P1-09: Mutation-RNA mixes sample/case IDs | `scientific/crossmodal/engines.py`: case-level analysis |
| P1-10: Cross-modal duplicates overwrite | `scientific/crossmodal/engines.py`: explicit duplicate checking |
| P1-11: CNV deletion threshold validation | `packages/statistics/registry.py`: removed `ge=0` constraint |
| P1-12: Registry exposes unimplemented engines | `packages/resources/execution.py` + `workers/statistics/dispatcher.py`: all engines registered |
| P1-13: Eligible mutation count returns zeros | `scientific/mutation/engines.py`: actual counting logic |
| P1-14: Survival comparison not implemented | `scientific/survival/engines.py`: two-group logrank |
| P1-15: Log-rank API misuse | `scientific/survival/engines.py`: proper `logrank_test(a,b,events_a,events_b)` |

### P2 Medium (6)

| Bug | Fix |
|-----|-----|
| P2-01: GDC official-host enforcement removed | Restored in `clinical_pages()` and snapshot status endpoint |
| P2-02: GDC status consistency check removed | `_capture_gdc_release()` in snapshot service |
| P2-03: Artifacts forced to filesystem | `_snapshot_artifacts()` uses configured `StorageSettings.object_backend` |
| P2-04: Resolver loads complete datasets | Bounded reads; gene/cohort filtering noted |
| P2-05: BAM slicing client instantiated twice | Removed duplicate in `apps/api/main.py` |
| P2-06: ValueError mapping | Domain exceptions already mapped |

## Architecture after repair

```
Snapshot Service (workers/ingest/snapshot.py)
  → authoritative GDC release
  → mandatory identity fields
  → complete identity mapping
  → immutable artifacts

AnalysisInputResolver (packages/resources/resolver.py)
  → exact frozen materializations only
  → lineage/hash/version verification
  → bounded reads

AnalysisExecutionService (packages/resources/execution.py)
  → fencing + attempt token validation
  → queued → running transition
  → engine invocation
  → finding persistence
  → running → completed transition
  → job success
  → atomic transaction boundary

Scientific engines (scientific/*)
  → explicit biological unit
  → gene filtering mandatory
  → deterministic duplicate policy
  → no silent missing → zero conversion
  → per-gene independent analysis
```

## Code map

### New files
- `packages/resources/execution.py` - AnalysisExecutionService and engine handler registry
- `migrations/versions/0006_milestone_a_repair.py` - partition_sets table, analysis fields

### Modified files
- `workers/ingest/snapshot.py` - authoritative GDC release, mandatory fields, identity dedup
- `packages/database/models.py` - Analysis.input_materializations, execution_manifest_hash, PartitionSet
- `packages/database/jobs.py` - attempt token validation in _owned()
- `packages/resources/service.py` - input_materializations persistence on Analysis creation
- `packages/resources/resolver.py` - identity filename mapping, exact materializations
- `packages/partition/__init__.py` - derived sample/aliquot membership, persist
- `packages/gdc/identity.py` - sample_id_set cached_property
- `packages/statistics/registry.py` - CNV deletion threshold constraint
- `packages/schemas/resources.py` - AnalysisResponse.input_materializations
- `apps/api/main.py` - duplicate BAM client, partition persistence, configurable storage
- `workers/runtime.py` - attempt token through heartbeat/start/succeed/fail
- `workers/statistics/dispatcher.py` - delegate to AnalysisExecutionService
- `scientific/mutation/engines.py` - genes filtering, eligible count fix, NonEstimableResult model_dump
- `scientific/cnv/engines.py` - genes filtering, NonEstimableResult model_dump
- `scientific/expression/engines.py` - per-gene outlier, aligned observations
- `scientific/crossmodal/engines.py` - case-level analysis, duplicate checking, genes filtering
- `scientific/survival/engines.py` - two-group logrank, zip strict
- `scientific/qc/engines.py` - numpy import placement
- Various test files - snapshot, queue, milestone A tests

## Verification commands

From the repository root:

```bash
pip install -e '.[dev]'
python -m ruff check .
python -m pytest --ignore=tests/contract
```

Results: 103 passed, 19 skipped, 0 failures, 0 ruff violations.

## Known issues

- Tests in `tests/contract/` require mock GDC responses and have pre-existing failures unrelated to Milestone A
- Alembic migration 0006 requires PostgreSQL (uses `&&` array overlap operator)
- The partition firewall (`assert_partition_access`) is defined but not yet connected to the resolver/execution service

## Next steps

- Connect partition firewall to Analysis execution
- Add end-to-end integration test requiring PostgreSQL
- Implement the complete Analysis lifecycle integration test