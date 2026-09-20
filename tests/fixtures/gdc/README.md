# Open GDC fixtures

These are real open TCGA-LUAD source excerpts, acquired on 2026-09-20 UTC, not synthetic
substitutes. The complete molecular payloads were acquired once for compatibility
inspection and verified against their GDC metadata MD5 and byte size before extraction.
This fixture acquisition is not a production downloader or bulk-download orchestration.

| Fixture | GDC file UUID / source | Workflow |
| --- | --- | --- |
| `mutation.maf` | `009254a2-ea81-4c76-8044-7267a9f81364` | Aliquot Ensemble Somatic Variant Merging and Masking; WXS masked somatic MAF |
| `rna.tsv` | `0052ae83-7ae5-470a-a125-5cd94a9fa9e9` | STAR - Counts; RNA-Seq gene expression |
| `gene_cnv.tsv` | `00286821-c3a3-4cc2-984d-f072c325f957` | ASCAT3; Genotyping Array gene-level copy number |
| `segment.tsv` | `0102ffb2-a483-4215-a97e-facec20945e2` | DNAcopy; Genotyping Array masked copy-number segment |
| `clinical.json` | `https://api.gdc.cancer.gov/cases` | One complete API page, TCGA-LUAD, size 1; diagnoses, follow-ups, demographics, exposures |

Each molecular `*.metadata.json` contains the exact files API hit, original filename,
MD5/size, identity links, acquisition timestamp, download endpoint and extraction recipe.
The molecular excerpts retain leading comments, header, and first eight data rows.
MAF was decompressed before extraction. RNA includes all four STAR summary rows.
Gene CNV deliberately includes both missing and observed source copy numbers.
Clinical metadata records the exact request URL and acquisition context.

`fixture_md5` and `fixture_sha256` authenticate each extracted fixture's UTF-8/LF bytes;
`.gitattributes` fixes checkout line endings. The original GDC MD5 and size are **not**
the excerpt's checksum and size. Tests create an explicitly derived frozen test source
with the excerpt filename/checksums while retaining the source identities and metadata
tuple. They never assert that excerpts are byte-identical to the complete upstream file.

Supplemental fault and scale generators live in `test_gdc_parsers.py` and the durable
integration tests. Their generator policy is `synthetic-test-variants-v1`, seed: none
(literal deterministic transforms, no randomness). These create malformed values,
ambiguous links, gzip with `mtime=0`, repeated rows, and missing/multiple diagnoses.
They supplement actual format compatibility, rather than serving as its sole evidence.

The complete acquired payload compatibility run accepted 175 MAF rows, 60,660 RNA gene
rows (excluding four STAR summaries), 60,623 gene CNV rows, and 453 segments. Each used
at most 512 buffered output rows; the complete source files are not committed.
