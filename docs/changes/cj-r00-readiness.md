# CJ-R00 readiness gate

## Task

Repair the restored PR09 foundation at `2bf6c68d93741b9974f46983e0a35c691d69c1f1`
without importing discarded milestone code or beginning CJ-R01.

## Architecture decision

Existing owners were extended rather than replaced. PostgreSQL remains authoritative
for resource and operational metadata, CAS remains authoritative for immutable bytes,
`packages/resources` owns Analysis/Finding transactions, deterministic code owns
scientific truth, workers remain execution adapters, and `packages/gdc` owns the
public-data boundary. No new external infrastructure or provider was introduced.
No new ADR was required because the approved R00 architecture and ownership map were
implemented without moving an authority boundary.

## Implementation

- Included all runtime packages in the wheel and proved imports outside the checkout.
- Added per-attempt job fencing, stale-worker rejection, terminal reaping, and
  migration `0005` with Cohort/Finding immutability.
- Added snapshot identity v2 over normalized case/sample/aliquot/file/link records and
  deterministic conflict rejection while preserving legacy v1 reads.
- Centralized scientific identity, rejected conflicting molecular duplicates and
  non-finite inputs, reconciled eligibility with analyzed observations, and moved
  Finding identity/publication authority into the resource service.
- Connected `run_analysis_from_artifacts` through the statistics worker and the narrow
  `AnalysisExecutionService`/`cnv_rna` registry using frozen verified CAS inputs.
- Added terminal `UNAVAILABLE_ACCESS` handling, executable credential-surface scans,
  complete-BAM denial, and quarantine for the generic complete-file transfer path.
- Replaced interactive frontend lint, upgraded Next to 16.3.5 to remove the audited
  PostCSS path, added a focused Chromium journey, reproducible Docker contexts,
  configurable loopback ports, provider-independent health, two-project Compose
  smoke, and split Python/PostgreSQL/frontend/Compose CI jobs.

## Files and owners changed

- Build and delivery: `pyproject.toml`, Dockerfiles, `.dockerignore` files,
  `compose.yaml`, `.github/workflows/ci.yml`, and `apps/web` configuration/tests.
- Operational persistence: `packages/database`, migration `0005`, worker runtime, and
  fenced queue/PostgreSQL tests.
- Snapshot/public data: `workers/ingest/snapshot.py`, `packages/gdc`, snapshot schemas,
  and policy/identity contract tests.
- Deterministic execution: `scientific/crossmodal`, `packages/statistics`,
  `packages/resources`, the statistics worker, and scientific/integration tests.
- Current-truth documentation: root architecture/README, milestone status, researcher,
  worker, getting-started, and Docker guidance.

## Verification performed

Verified on 2026-09-22:

- Python 3.12.14, pytest 8.4.2, PostgreSQL 16: `176 passed, 2 warnings`.
- Python 3.14.3 host cross-check: `176 passed, 398 warnings`; the warnings are the
  known unsupported-runtime asyncio/Windows cleanup behavior, not test failures.
- Ruff 0.16.8: passed.
- Alembic: one head, `0005`; migration upgrade/downgrade/upgrade and immutable/fencing
  behavior are covered by the PostgreSQL suite.
- `python -m build`: sdist and wheel built; wheel content and isolated imports passed.
- Node 24.13.1, npm 11.8.0: clean install, lint, typecheck, Next 16.3.5 build, and
  `npm audit --omit=dev` passed with zero vulnerabilities.
- Playwright 1.63.0 / Chromium: one focused snapshot-screen journey passed with the
  API response intercepted; no live provider dependency or credential UI is used.
- Docker 29.8.0 / Compose 5.5.1: images built; projects `cancerjev-r00-a` and
  `cancerjev-r00-b` ran simultaneously on distinct loopback ports. Both smoke runs
  verified API/web health, migration `0005`, both workers, and all nine cross-service
  MinIO CAS reads. Test projects and volumes were removed afterward.

## Compatibility and data ownership

Legacy snapshot/Finding rows remain readable and are not relabeled with provenance
that was never recorded. New snapshot writes use identity v2. New claims receive an
attempt token. Public API callers and workers cannot author Finding IDs or result
hashes. No authoritative data owner moved.

## Known limitations and deferrals

- The API remains local-development-only until CJ-R06 adds runtime isolation and
  service authorization without end-user accounts.
- The complete acquisition planner and bounded open-BAM slicer remain CJ-R04 work;
  current unsafe complete transfer paths fail closed.
- Only the existing `cnv_rna` engine is registered. Later scientific engines remain
  assigned to their roadmap milestones.
- ESLint 9.39.1 is the newest tested compatible major for the current Next plugin;
  ESLint 10.11.0 was rejected because `eslint-plugin-react` fails at runtime.
- Compose is a development topology. Production deployment, secrets, backups, and
  recovery remain CJ-R33 work.

## Result

CJ-R00 acceptance is satisfied. CJ-R01 is unblocked but was not started.
