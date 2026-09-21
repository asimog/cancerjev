# Public GDC-derived test fixtures

These small fixtures model public GDC formats for deterministic parser tests. They are
not full upstream files and are never evidence for a biological claim.

| Fixture | Contract exercised |
| --- | --- |
| `mutation.maf` | mutation identity, gene/coordinate, parser diagnostics |
| `rna.tsv` | STAR expression measurements and exclusions |
| `gene_cnv.tsv` | gene-level copy-number materialization |
| `segment.tsv` | segment coordinate/value validation |
| `clinical.json` | public clinical missingness and diagnosis structure |

Sidecar metadata supplies frozen public-file identity. Tests may mutate copies to
exercise checksum, access, schema, and identity rejection. Do not replace fixtures
with controlled records, tokens, raw/full BAMs, or personally identifying data.
