# PR09: canonical architecture and GDC/storage hardening

## Requested and inspected

Started `codex/pr09-architecture-gdc-hardening` from `origin/main` at `8cf6cc0`,
which includes merged PR #8. Inspected merged history #1–#8, the README/architecture,
ADRs 001–002, PR #8 change record, GDC adapter and filters, snapshot orchestration,
PR #8 source/materialization services and identity resolver, resource schemas,
repositories, migrations, storage configuration, worker entrypoints and tests.
The original checkout had unrelated uncommitted statistics work; this PR was built
in a separate worktree without modifying that work.

## Architecture test and implementation plan

Classification: **Large**, authorized by the explicit request for these contract,
policy, documentation and persistence changes.

- Problem: runtime admission paths were weaker than the architecture's frozen,
  open-only scientific authority; Compose configured no shared object backend.
- Existing owners: GDC adapter owns upstream integration; resource service owns
  cohort/analysis admission and metadata transactions; PostgreSQL owns durable
  records; storage owns bytes; PR #8 owns parsing/materialization.
- Reuse: keep parsers, format registry, verified staging, identity graph, CAS and
  materialization repositories. Extract the existing graph reader for sharing.
- Contracts: remove caller release labels and unrestricted manifests, require
  materialization/modality/measurement references on new analyses, and add a
  snapshot-scoped manifest operation. External GDC endpoints remain behind its adapter.
- Persistence: additive migration 0004 records analysis input bindings and freezes
  their scientific fields and snapshot artifact links. Status provenance uses existing
  immutable snapshot/artifact resources. No new domain subsystem or dependency.
- Dependency direction: API/workers call resource services; services resolve
  repository/storage contracts; parsers remain independent of database/storage SDKs.
- Simplest solution: enforce policy once at file pagination, reuse the frozen graph,
  validate durable lineage, and share real StorageSettings keys in Compose.
  Alternatives and migration consequences are recorded in ADR-003.
- Risks/edge cases: missing access, caller filters/fields, redirects/auth headers,
  release changes, empty and foreign manifests, upstream metadata drift, impossible
  sample parents, cross-snapshot lineage, measurement mismatch, historical records,
  unavailable/corrupt bytes and cold container initialization.
- Regression surface: snapshot identities, metadata adapter callers, source readers,
  cohort/analysis API contracts, migrations, CAS and worker startup. GDC parser outputs
  and scientific engines remain unchanged.
- Initial confidence: **8/10**. Ownership and contracts were traceable; live GDC
  response types and actual Compose storage behavior required verification.
- Order: inspect → central policy/status → shared frozen reader and admission checks
  → migration/CAS wiring → regression tests → runtime verification → diff review/PR.
- Done criteria: requested invariants enforced, canonical docs/ADR current, Ruff,
  full PostgreSQL pytest, migration roundtrips, Compose build and shared CAS smoke,
  final diff reviewed, PR opened against main without merging.

## Completed implementation

The README is replaced and the supplied canonical architecture is incorporated with
explicit implemented/planned labels. Jev's previously reverted implementation and
the unconnected artifact-statistics worker are described truthfully.

`packages/gdc/policy.py` restricts production authority to the official host.
Every file discovery adds the open-access filter and validates response access;
caller fields cannot suppress the check. Credentials and redirects fail closed.
The adapter now exposes documented status/version/history/mapping operations.
Snapshot creation binds before/after status to immutable identity/provenance and
rejects caller release strings or a release change during discovery.

The resource-level frozen reader reuses PR #8's staging/identity implementation.
Cohorts validate case/sample membership and parent relationships. Manifests resolve
published snapshots and validate both requested subsets and returned metadata.
New analyses require compatible materializations, derive output hashes and retain
explicit immutable input bindings. Existing cohorts are checked again at admission.

Compose shares MinIO settings across API/ingest/statistics and waits for bucket
initialization. New API snapshot artifacts publish to CAS; consumers do not require
the publisher's snapshot directory. Historical local artifact reads are retained.
Pinned MinIO images now use Quay because Docker Hub pulls failed. PostgreSQL has a
120-second initialization grace period after a cold-volume startup exceeded the
old healthcheck budget. Next.js now binds explicitly and its probe uses IPv4 instead of IPv6 localhost.
These are runtime fixes, not relaxed scientific tests.

Live upstream probes exposed a preexisting gzip double-decode in the bounded HTTP
reader; decoded response headers now match the decoded body. The live manifest
also confirmed GDC uses validated storage state for released open files, so safe
manifests accept validated/released states while rejecting deleted states.

The original materialization concurrency regression exposed Windows replacement
of a concurrently published/open CAS file. Filesystem writes now publish through
an exclusive hard link, verify concurrent winners, and use unique temporary files
for both byte and file inputs. Corrupt existing objects are rejected. The public
storage contract and scientific materialization remain unchanged.

## Files and decisions

- `README.md`, `ARCHITECTURE.md`: canonical description and current-state map.
- `packages/gdc/{policy,client,filters,manifest,mappings/identity}.py`: upstream policy.
- `workers/ingest/snapshot.py`, `packages/schemas/snapshot.py`: status-derived identity.
- `packages/resources/{snapshots,materialization,service}.py`: shared frozen context and admission.
- `packages/schemas/resources.py`, `packages/database/models.py`, migration 0004: input binding.
- `apps/api/{config,main}.py`: official host, safe manifest API and CAS publication.
- `compose.yaml`, `scripts/compose_smoke.py`: shared bucket and executable runtime checks.
- `packages/storage/objects.py`: exclusive immutable local CAS publication.
- Contract, storage, snapshot and durable-resource tests: regression coverage and valid frozen fixtures.
- [ADR-003](../adr/ADR-003-gdc-trust-and-shared-storage.md): all decisions, alternatives and migration impact.

## Verification

Executed on 2026-09-21 with Python 3.14, disposable PostgreSQL 16 and Docker Desktop:

- `python -m ruff check .`: passed, including the final smoke-script edits.
- `python -m pytest -q --disable-warnings --basetemp .data/pr09-verified`, with the
  disposable database URL configured: **128 passed, zero skipped**, 344 warnings,
  200.65 seconds. Warnings were not treated as errors.
- The full suite includes PR #8 parser/materialization regressions, concurrency and
  parser-version separation; all new source-policy/admission checks; legacy path and
  CAS-only snapshot readers; and atomic byte/file CAS publication/corruption tests.
- Migrations: fresh 0001 → 0004; 0004 → 0002 → 0004 preserving PR #7 resources;
  0004 → 0003 → 0004 preserving historical analysis columns without inventing input
  bindings. Explicit `python -m alembic upgrade head` / `current`: **0004 (head)**.
- Python wheel build passed. Compose built backend and Next.js production images.
  The final backend image was rebuilt from the final source with `docker compose
  -p cancerjev-pr09 build api`, then tagged for ingest/statistics/migrate, whose
  Dockerfile and build context are identical. No container source files were patched.
- `docker compose -p cancerjev-pr09 up -d --no-build --wait --wait-timeout 120`:
  passed with API, web, PostgreSQL and MinIO healthy, both workers running, and
  migration/bucket initialization exited successfully.
- `python scripts/compose_smoke.py --project cancerjev-pr09`: passed. Each service
  writes a fresh object using its own environment; all three verify all three objects
  through MinIO (**9 reads**). The script checks database migration, API/web HTTP
  responses and actual container health status.
- Live official GDC probes passed for `/status`, `/projects`, `/cases`, `/files`,
  `/files/versions/{uuid}`, `/history/{uuid}`, `/files/_mapping` and one-file `/manifest`.
  Observed API version 1 and Data Release 46.0; manifest metadata was checked against
  the freshly frozen adapter probe. No molecular payload was downloaded. Durable
  snapshot lookup and rejected manifest subsets were covered separately in PostgreSQL tests.
- Reviewed the full staged diff and ran `git diff --cached --check`: passed. Confirmed
  the original checkout's uncommitted statistics files were unchanged.

Intermediate failures were resolved: an invalid two-snapshot test fixture reused a
unique snapshot hash; live gzip responses were decoded twice; Windows concurrent CAS
replacement failed; the old MinIO image registry could not supply pinned images;
PostgreSQL cold initialization exceeded the old probe budget; and web health used an
unbound hostname/IPv6 address. No assertions were weakened to conceal these failures.
The final full pytest run followed all production-code fixes; subsequent changes were
limited to Compose health probing, smoke diagnostics and documentation, then verified
by the final Compose run above.

## Known limitations

No Jev, new scientific engine, artifact-analysis executor, production deployment or
bulk acquisition orchestration was added. Engine-specific input sufficiency and
scientific compatibility policies remain future work; this PR validates declared
snapshot/modality/measurement lineage. Existing SHA-only analyses remain readable
without invented bindings. Downgrading 0004 loses newly stored bindings.

Status bracketing cannot make paginated upstream discovery atomic. Cross-store
failures can leave unreferenced immutable objects. Bucket Object Lock/retention and
orphan cleanup remain deferred. Historical filesystem resources still need their
original snapshot root. There is no configured static type checker.


## Final review and handoff

No new dependency, scientific engine, parser implementation or semantic subsystem was
introduced. Data ownership remains PostgreSQL metadata plus immutable CAS bytes.
The shared graph reader replaces the prior private implementation rather than creating
another parser/identity system. See ADR-003 for breaking request contracts and downgrade
consequences. The remaining next step is review of this PR; automatic merge is not enabled.
