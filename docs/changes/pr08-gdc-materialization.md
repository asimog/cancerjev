# PR #8: real GDC parsers and durable canonical materialization

## Result and ownership

Replaced the canonical-column TSV prototype and arbitrary-path ingest jobs with verified
GDC format parsers, frozen identity resolution, bounded Parquet materialization, and
durable source-to-output lineage. This approved Large change stays within the existing
GDC adapter, canonical schemas, storage, resource service/repositories, and ingest worker.
PostgreSQL remains the metadata owner; immutable scientific bytes remain in object storage.
No dependencies, downloader, statistical engine, or UI were added.

## Supported formats and registry

All parsers are version 1 and emit canonical schema version 2. Registry matching is exact:

| Modality | Supported GDC type / strategy / workflow / format |
| --- | --- |
| Mutation | Masked Somatic Mutation / WXS / Aliquot Ensemble Somatic Variant Merging and Masking / MAF, including gzip |
| RNA | Gene Expression Quantification / RNA-Seq / STAR - Counts / TSV |
| Gene CNV | Gene Level Copy Number / Genotyping Array / ASCAT3 / TSV |
| Segment CNV | Masked Copy Number Segment / Genotyping Array / DNAcopy / TXT |
| Clinical | Official cases API JSON pages with frozen case membership and acquisition provenance |

The registry also checks data category and requested parser version. Its protocol exposes
name/version, supported metadata, output model/schema version, identity level and measurements.
See [the complete contract](../architecture/gdc-materialization.md).

## Schema, identity, and measurements

- Molecular v2 retains source gene IDs, version suffixes and explicit normalization version.
  `ensembl-gene-suffix-v1` strips numeric Ensembl versions while preserving `_PAR_Y`.
- Mutation SSM IDs and gene CNV classes are optional. No fabricated IDs or classes are emitted.
  Mutation annotations include source barcode, transcript, protein, classification/consequence
  and end coordinate. Segments retain aliquot and probe count and remain separate from gene CNV.
- UUIDs and exact submitter IDs resolve only through frozen file/case/sample/aliquot relationships.
  MAF and segment UUID fields identify aliquots. Missing, conflicting and ambiguous identities
  have structured diagnostics. The primary-tumor policy retains eligible ties and logs exclusions.
- RNA artifacts separate unstranded counts, both stranded count measurements, TPM, FPKM and
  FPKM-UQ using the exact six STAR measurement labels. Four named STAR summary rows are excluded.
- Clinical records preserve demographics, diagnoses, follow-ups and exposures without deriving
  survival endpoints. Missing time and status remain missing; multiple diagnoses remain distinct.

## Storage, hashing, and lineage

Molecular source registration checks frozen UUID, filename, byte size and GDC MD5. All stored
sources additionally use SHA-256. Workers stage verified private copies, stream gzip/plain rows,
write bounded explicit-schema Parquet batches, and persist streamed diagnostics.

Physical SHA-256 identifies exact bytes. Logical SHA-256 hashes canonical validated rows in source
order with a schema/encoding prefix, independently of row-group boundaries. Materialization identity
includes frozen snapshot/source binding plus parser/schema/normalization/selection versions and
modality/measurement. Physical Parquet stability across software versions is not promised.
Duplicate source observations are retained. Empty valid inputs yield correctly typed empty files.

Migration **0003** adds immutable `materialization_sources` and `materializations`, referencing
existing DatasetSnapshot/DatasetObject resources. `0002` is unchanged. Derived SnapshotArtifact
associations expose output artifacts without mutating published snapshot identity. Workers can query
snapshot/modality/measurement directly. Concurrent retries converge through database uniqueness;
parser version changes retain distinct lineage even when physical output is identical.

File/S3 storage shares the existing object-store protocol with a verified staging operation.
Runtime settings select the backend. Existing PR #7 snapshot-relative artifacts remain supported.
The strict worker request carries snapshot/source IDs, expected source digest, modality, parser
version and measurement; it rejects legacy unrestricted path payloads.

## Implementation map

- `packages/gdc/{parsers,identity,normalization,materialization}.py`: parsing, resolution,
  gene policy, source checks, canonical logical hashing, bounded writer and diagnostics.
- `packages/gdc/client.py`: frozen-membership clinical API acquisition and aliquot submitter metadata.
- `packages/schemas/{molecular,materialization}.py`: molecular v2 and compact job contracts.
- `packages/resources/{materialization,service,repositories}.py` and database repositories/models:
  acquisition registration, context resolution, transactional lineage and lookup contracts.
- `packages/storage/{objects,config}.py`, API config and `.env.example`: bounded verified object
  staging, concurrent file publication and shared backend settings.
- `workers/ingest/materialize.py`: durable compact worker entry point.
- `migrations/versions/0003_gdc_materialization.py`: additive lineage migration and immutability.
- Parser/clinical/storage and PostgreSQL integration tests; real fixtures with source provenance.
- Root architecture map, ADR-002 and current materialization documentation.

## Executed verification

On 2026-09-20, using Python 3.14 and an isolated PostgreSQL 16 container:

- `python -m ruff check .`: passed.
- `python -m pytest -q --disable-warnings --basetemp .data/pr08-pytest-final`, with the disposable
  `CANCERJEV_DATABASE_URL` configured: **88 passed, zero skipped**, 164 dependency deprecation warnings.
- Full suite includes migration 0001 -> 0002 -> 0003, 0003 -> 0002 -> 0003 preserving PR #7 resources,
  all five durable fixture flows, concurrent retries, rollback, parser-version separation, compact
  worker execution, existing PR #7 snapshot-path compatibility and clinical acquisition registration.
- Parser coverage includes real formats, RNA separation/special rows, gzip, empty valid files,
  malformed headers/rows, invalid alleles/coordinates/non-finite values, checksum/size/UUID failures,
  unknown parser combinations, missing/conflicting/ambiguous identities, duplicates, normalization,
  deterministic logical output, partial generator consumption and 10,003 rows buffered in batches of 17.
- `python -m pip wheel --no-deps . --wheel-dir .data/pr08-dist`: passed.
- S3 staging/checksum behavior passed with a mocked client; no live S3 service was exercised.

The verified fixture flow ran through parser -> frozen resolver -> canonical Parquet -> File object
storage -> actual PostgreSQL DatasetObject/lineage registration for all five modalities.

Full acquired molecular payloads were also verified against original GDC MD5 and size, then parsed:

| Source UUID | Accepted | Excluded | Rejected | Maximum buffered rows |
| --- | ---: | ---: | ---: | ---: |
| `009254a2-ea81-4c76-8044-7267a9f81364` (MAF) | 175 | 0 | 0 | 175 |
| `0052ae83-7ae5-470a-a125-5cd94a9fa9e9` (RNA TPM) | 60,660 | 4 STAR summaries | 0 | 512 |
| `00286821-c3a3-4cc2-984d-f072c325f957` (gene CNV) | 60,623 | 0 rows | 0 | 512 |
| `0102ffb2-a483-4215-a97e-facec20945e2` (segments) | 453 | 0 | 0 | 453 |

These are observed compatibility results for these sources, not a claim of compatibility with all
GDC releases. Committed fixture provenance records exact source metadata, endpoint, acquisition time,
extraction and excerpt checksums. Synthetic fault/scale variants are deterministic and labeled.

## Limitations and remaining work

Unsupported: VCF, other MAF callers/workflows, HTSeq/single-cell RNA, other gene/segment CNV workflows,
clinical XML/TSV, controlled access, non-Ensembl gene mappings, and unknown metadata combinations.
Older frozen snapshots without aliquot barcodes can use authoritative UUIDs but cannot resolve an
otherwise unknown barcode alone. Genomic rows remain source-ordered; duplicates are not collapsed.

Clinical pages are limited to 8 MiB, molecular lines to 1 MiB, and output batches to 65,536 rows.
Identity metadata is indexed in memory; large molecular input/output is staged on disk. Cross-store
registration failures may leave orphan immutable objects; garbage collection remains deferred.
Live S3 and a live end-to-end clinical acquisition-to-database transaction were not exercised;
clinical real-payload parsing and the connected acquisition path were verified separately.

PR #9 still owns artifact-backed statistics/discovery, CNV recurrence semantics and survival endpoint
construction. PR #14 still owns official gdc-client production acquisition and live full acceptance
orchestration. Findings/Graph, UI, and Jev remain outside this change.

The integration suite recreates the PostgreSQL public schema: reproduce it only against a disposable
test database. No static type-checker is configured in this repository.
