# GDC canonical materialization

```text
Frozen snapshot metadata and identity artifacts
  + acquired source registered after UUID/name/size/MD5 verification
  -> compact materialization job
  -> verified private source staging
  -> explicit parser registry + frozen identity resolution
  -> canonical v2 records + streamed diagnostics
  -> bounded Parquet writer
  -> existing File/S3 content-addressed object store
  -> DatasetObject + immutable source/materialization lineage
```

## Supported registry (parser version 1, canonical schema version 2)

Selection matches modality, category, type, experimental strategy, workflow, format,
and parser version exactly. Unknown combinations and unknown RNA measurements fail.
The clinical parser is selected only for registered cases API sources.

| Parser / modality | GDC category / type | Strategy / workflow / format |
| --- | --- | --- |
| `gdc-masked-maf` / mutation | Simple Nucleotide Variation / Masked Somatic Mutation | WXS / Aliquot Ensemble Somatic Variant Merging and Masking / MAF |
| `gdc-star-counts` / expression | Transcriptome Profiling / Gene Expression Quantification | RNA-Seq / STAR - Counts / TSV |
| `gdc-ascat3-gene-cnv` / cnv | Copy Number Variation / Gene Level Copy Number | Genotyping Array / ASCAT3 / TSV |
| `gdc-dnacopy-masked-segment` / segment_cnv | Copy Number Variation / Masked Copy Number Segment | Genotyping Array / DNAcopy / TXT |
| `gdc-cases-clinical` / clinical | Clinical / GDC Cases | API / JSON; no molecular file UUID |

`packages/gdc/parsers.py` owns the `Parser` protocol and registry. Names, versions,
output models, schema versions, required identity levels, and measurements are explicit.
No generic canonical-column TSV fallback remains in the ingest worker.

## Identity and scientific semantics

The resolver validates frozen case/sample/aliquot/link relationships and indexes them.
MAF `Tumor_Sample_UUID` and segment `GDC_Aliquot` resolve aliquots, not samples.
UUID/barcode matches are restricted to the file's frozen links. Known conflicting
identifiers fail. Exact frozen barcodes may resolve identity without UUIDs. Older
snapshots without aliquot barcodes may resolve a supplied UUID; an unrecognized
payload barcode is preserved as source annotation and is not used as identity evidence.
New snapshots request aliquot submitter IDs explicitly.

`primary-tumor-retain-ties-v1` reuses existing primary-tumor semantics. Matched normal
samples are excluded explicitly and listed in the diagnostics artifact. Distinct
qualifying primary samples are retained in the resolver. An unresolved multi-sample
file is rejected row by row with candidate counts; no first-UUID selection occurs.
Sample-level files with several aliquots of the same sample retain a null aliquot.
MAF and segment parsers require resolvable aliquot identity.

Mutation records retain source file, barcode, source gene, symbol, coordinates,
alleles, classification/consequence, protein and transcript information. SSM identity
is optional. Coordinates and alleles are validated. Gene CNV retains source copy
number/min/max including missing values; no derived classification is assigned.
Segments remain separate, with ordered positive coordinates, optional nonnegative
probe counts, and finite segment means.

`ensembl-gene-suffix-v1` retains source Ensembl identifiers and version suffixes,
removes numeric gene versions from canonical IDs, and retains `_PAR_Y` distinctions.
Other namespaces are rejected rather than mapped through online lookups or symbols.

RNA measurements are separate artifacts and have explicit row labels:
`unstranded`, `stranded_first`, `stranded_second`, `tpm_unstranded`,
`fpkm_unstranded`, `fpkm_uq_unstranded`. Counts must be integral and all values finite
and nonnegative. Only `N_unmapped`, `N_multimapping`, `N_noFeature`, and `N_ambiguous`
are excluded as STAR non-gene summaries. Unexpected identifiers are rejected.

Clinical acquisition uses bounded official `/cases` JSON pages, restricted to frozen
case UUIDs. Endpoint, query, acquisition timestamp, source bytes and digest are stored.
Clinical records preserve demographics and each diagnosis separately, with nested
diagnosis, follow-up and exposure fields encoded as canonical JSON strings. Cases
without diagnoses retain their supplied case/demographic observation. No survival
time or censoring status is inferred; source missingness remains null. Endpoint
derivation is deferred to PR #9.

## Bounded processing and errors

`materialize_verified` is the narrow local-payload API. It verifies a private staged
copy before parsing. Molecular registration additionally checks original filename
association and frozen file UUID, size, and MD5; independent SHA-256 authenticates
stored sources. Clinical API responses use their recorded SHA-256 and size, without
inventing a GDC file ID or upstream MD5.

TSV/MAF readers stream plain or gzip bytes. A line is capped at 1 MiB. Clinical API
pages are capped at 8 MiB before JSON decoding and at parser input; acquisition uses
at most 100 frozen cases per query. Molecular records buffer at most the configured
batch size (default 4096, range 1..65536). Identity indexes scale with frozen cohort
metadata, not molecular row count. Disk staging scales with input/output size.

Malformed headers, unsupported formats, corrupt compression, or failed checksums fail
the materialization. Row validation and identity failures yield bounded reason counters
plus streamed per-row diagnostics. Source row order and duplicate observations are
preserved, not silently deduplicated. Empty valid headers produce zero-row Parquet with
the complete explicit Arrow schema. No empty observation is fabricated.

Parquet uses explicit ordered fields, int64/float64/string scalar types, zstd level 3,
format 2.6, no dictionary encoding, and statistics. These settings do not promise
physical byte identity across Arrow versions or different row-group boundaries.

## Durable lineage and hashes

Migration `0003` adds immutable `materialization_sources` and `materializations` in
the existing database. `DatasetObject` remains the only physical artifact registry;
`0002` is unchanged. Source bindings link snapshot and source object, GDC metadata
or clinical provenance. Materializations link source, output, diagnostics, parser,
schema, normalization/selection versions, modality, measurement, content hash and counts.
SnapshotArtifact also exposes derived output associations without modifying snapshot identity.

Three identities have different meanings:

1. Physical object SHA-256: exact stored source, Parquet or diagnostic bytes.
2. Logical content SHA-256: schema-prefixed `canonical-json-lines-v1`, followed by
   canonical validated rows in source order. Independent of batch size; not invariant
   to reordered source rows. Non-finite numeric values are forbidden.
3. Materialization ID: hash of frozen snapshot/source binding plus parser, schema,
   normalization, selection, modality and measurement versions. Different parser
   versions remain distinct even if physical output is shared. Reacquisition clock
   changes do not change source binding identity; first registered provenance is retained.

The resource service publishes objects before registering output, diagnostics, lineage,
snapshot association and audit in one transaction. Unique IDs and savepoints reconcile
concurrent retries. Failed transactions can leave unreferenced immutable bytes, as in
PR #7; garbage collection is not part of this change.

Workers can query `DurableResourceService.list_materializations(snapshot_id,
"expression", "tpm_unstranded")`; storage filenames are not parsed for scientific identity.

## Application entry points

Run `alembic upgrade head` against the intended database before deploying the worker.
Use `StorageSettings` for `CANCERJEV_OBJECT_BACKEND=filesystem|s3`, `OBJECT_ROOT`,
`OBJECT_BUCKET`, and optional `OBJECT_ENDPOINT_URL` (all names carry `CANCERJEV_`).
S3 uses standard AWS credential resolution. Existing PR #7 snapshot-relative artifacts
remain readable under configured `CANCERJEV_SNAPSHOT_ROOT`; new scientific objects use CAS.

Within a caller-owned resource transaction:

```python
service = MaterializationService(resources, settings.store(), settings)
source = service.register_local_source(snapshot_id, acquired_path, file_id=gdc_uuid)
```

This is a trusted acquisition API, not a remotely supplied worker path. For clinical
metadata, consume `service.acquire_clinical_sources(snapshot_id, gdc_client)` completely
inside the transaction, or register an already acquired bounded page with provenance.

The `materialize_snapshot` worker accepts only this strict resource contract:

```json
{
  "snapshot_id": "DS-...",
  "source_id": "sha256:<registered-source-binding>",
  "expected_source_sha256": "sha256:<source-bytes>",
  "modality": "expression",
  "parser_version": "1",
  "measurement_type": "tpm_unstranded"
}
```

Legacy arbitrary filesystem job payloads fail validation. Existing molecular schema
v1 callers must migrate to v2; snapshot identity schemas remain v1. No new dependency
or alternate downloader is introduced.

## Unsupported and deferred

VCF, legacy single-caller MAF workflows, HTSeq, single-cell RNA, ASCAT2/ABSOLUTE/other
CNV workflows, unmasked/allele-specific segment formats, clinical XML/TSV, non-Ensembl
gene mapping, controlled-access data, and unknown metadata combinations are unsupported.
Adding a variant requires explicit registry support and representative tests.

PR #9 owns statistics/discovery, endpoint derivation, CNV recurrence thresholds and
artifact-backed analysis execution. PR #14 owns live bounded official gdc-client bulk
acquisition and full acceptance orchestration. UI, Findings/Graph and Jev are unchanged.
