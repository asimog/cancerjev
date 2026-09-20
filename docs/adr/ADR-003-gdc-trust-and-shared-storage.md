# ADR-003: official GDC authority, frozen scientific inputs and shared CAS

Status: accepted for the explicitly requested PR09 hardening scope.

## Context

Merged PRs #1–#8 established metadata snapshots, durable resources and real GDC
parsers/materializations. PR #3 reverted the Jev integration. Generic file queries,
raw-ID manifests, caller release labels, unchecked cohorts and SHA-only analyses
could bypass the intended trust boundary. Compose's obsolete S3 setting silently
left services on separate filesystem stores.

## Decisions and ownership

1. `packages/gdc/policy.py` is the production host/access authority. Restrict all
   transport to HTTPS `api.gdc.cancer.gov`, reject authentication headers and
   redirects, AND every file discovery filter with explicit open access, and check
   returned access. Test transports use the same official URLs; no alternate-host
   production switch exists. Remove unused experimental endpoint wrappers.
2. Use documented metadata endpoints and capture complete `/status` documents on
   both sides of discovery. Reject changed status and include it in snapshot identity
   and immutable provenance. Caller release labels are removed. Existing snapshot
   and DatasetObject records already support this resource; a parallel status table
   would duplicate ownership and is unnecessary. Capture time is snapshot creation
   time, outside scientific identity. No atomic GDC read is claimed.
3. Manifest selection belongs to the resource service: resolve the durable published
   snapshot and its verified graph, then permit only frozen open IDs or a subset.
   Verify upstream manifest membership, filename, MD5 and size against that
   snapshot, and allow only validated/released transfer states. Live GDC manifests
   report validated for released open files. Version/history lookups are informational; they cannot replace inputs.
4. Extract PR #8's verified snapshot staging/graph reader into an explicit shared
   resource contract. Materialization, cohort creation, existing cohort validation
   during analysis creation, and manifest selection reuse it. Cohort sample parents
   must be among its selected cases. Empty cohorts remain representable; this does
   not certify their scientific usefulness. No parser or materializer is reimplemented.
5. Analysis requests require materialization IDs, modality and measurement contracts.
   Resolve and compare all three plus snapshot identity; derive the output hashes.
   Optional caller hashes are consistency assertions only. Persist these bindings in
   `analyses.input_materializations`. This is input admission, not a new engine or
   an engine-specific scientific compatibility registry. Migration 0004 prevents
   changes to analysis scientific inputs and frozen SnapshotArtifact associations.
6. Share a YAML environment anchor for S3 backend, bucket, endpoint and development
   credentials among API, ingest and statistics. New API snapshots copy verified
   artifacts to configured CAS before database registration. Existing local snapshot
   files remain a publication cache and support historical filesystem registrations.
   Workers wait for bucket initialization. Use the same pinned MinIO releases from
   Quay because their Docker Hub pulls failed during verification. Give PostgreSQL
   an initialization grace period, explicitly bind Next.js to 0.0.0.0 and probe
   127.0.0.1 to avoid localhost resolving to an unbound IPv6 address.
7. Filesystem CAS uses unique temporary files and exclusive hard-link publication.
   A losing concurrent writer verifies the winner's digest instead of replacing an
   immutable file that Windows readers may have open. Both byte and file publication
   share this operation; corrupt preexisting objects fail closed. This fixes the
   reproduced PR #8 concurrent materialization regression without changing its parser.
   The filesystem backend requires same-volume hard-link support (verified on NTFS).
8. Canonical documentation explicitly separates current deterministic capabilities
   from planned Jev, reasoning, evidence graph and deployment architecture.

## Alternatives and rationale

- Filtering only in `get_open_files` leaves generic pagination paths unprotected.
- Re-querying live membership for manifests/cohorts destroys reproducibility.
- Trusting any registered SHA loses snapshot, parser and measurement lineage.
- A new source/status subsystem duplicates existing immutable artifact/provenance
  storage. Reuse retains one owner and a smaller migration.
- Storing molecular matrices in jobs or adding a queue/object abstraction is not
  needed. Existing PostgreSQL jobs, File/S3 contracts and PR #8 parsers are retained.
- Extending the statistics runtime here would overlap separate engine work and is
  explicitly outside this PR.

## Compatibility and migration

Apply 0004 after 0003. Historical analyses receive an empty input-binding array;
no lineage is inferred from their SHAs. New create requests must adopt explicit
materialization references. Snapshot create clients must stop sending `gdc_release`.
Generic experimental GDC helpers and `manifest(file_ids)` are intentionally removed.
Older frozen snapshots lacking a complete verified graph cannot create new cohorts
or manifests. Legacy filesystem graphs remain usable with their snapshot root.

Downgrading 0004 removes the binding column and immutability triggers but preserves
old columns/rows. It loses new binding metadata, so downgrade is not a transparent
rollback for newly created analyses. The migration tests demonstrate this explicitly.

## Risks and limits

Metadata acquisition is bounded but GDC supplies no transaction across pages.
Status bracketing detects release changes only. Cross-store publication may leave
unreferenced immutable objects after transaction failure; garbage collection is
deferred. S3 credentials and bucket access are trusted deployment configuration.
Application immutability is enforced by verified hashes and database triggers;
bucket-level retention/Object Lock is not configured. Historical invalid resources
are not rewritten. Durable artifact-based analysis execution remains disconnected.

## Sources

- [Official GDC endpoints and host](https://docs.gdc.cancer.gov/API/Users_Guide/Getting_Started/)
- [File versions, history and mappings](https://docs.gdc.cancer.gov/API/Users_Guide/Search_and_Retrieval/)
- [PR #8 parser/materialization contract](../architecture/gdc-materialization.md)
