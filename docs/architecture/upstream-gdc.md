# NCI-GDC upstream adoption record

**Reviewed:** 2026-09-20. Commits are the heads of each repository's default branch at review time.
CancerJev copied no upstream source or assets, so no third-party text is reproduced in `NOTICE`.

| Repository | Default | Reviewed SHA | License | Use | Copied? | Runtime? |
|---|---|---|---|---|---|---|
| `NCI-GDC/gdc-client` | develop | `048983310277463893b7ab4a153a190340ec8b8b` | Apache-2.0 | Official external bulk/resumable transfer executable | No | Operator-installed executable |
| `NCI-GDC/gdcdictionary` | develop | `88d66b0fe361aa638977850c180bd9130d705924` | Apache-2.0 | Pinned field-semantics/schema reference for explicit mappings | No | No |
| `NCI-GDC/gdc-models` | develop | `f568d785915761b9c5902f9ce4d05e4aa9bbb11c` | **No repository license detected** | Read-only entity-graph reference; no code adoption | No | No |
| `NCI-GDC/gdc-workflow-overview` | master | `2412e93b3d7de8afb74ad6e28566e5a6b2e0ad1e` | Apache-2.0 | Harmonization concepts and provenance reference | No | No |
| `NCI-GDC/gdc-rnaseq-cwl` | master | `05460f7dfca5a900d7635ccae0e1b28cf764a02f` | Apache-2.0 | Provenance for consumed harmonized RNA outputs; never rerun | No | No |
| `NCI-GDC/gdc-dnaseq-cwl` | master | `ed98a652e8196296dc3cac7db2e1fa5723d237b4` | Apache-2.0 with documented CC-BY-SA-4.0 blocks | Provenance for harmonized mutation/CNV outputs; no BAM/FASTQ processing | No | No |
| `NCI-GDC/gdc-frontend-framework` | develop | `de23d8a9d2c3416217badedb89476b98c70ce916` | Apache-2.0 | Cohort, survival, visualization and terminology UX reference only | No | No |

## Boundary decision

GDC response JSON is transport input, never CancerJev's domain. `packages/gdc/mappings` maps selected
fields to strict CancerJev schemas. Schema upgrades therefore change a versioned mapping rather than
leaking upstream shapes into science. The biological chain is Project → Case → Sample → Aliquot → File;
missing links remain missing and are never inferred from another modality.

`gdc-client` is invoked using an argument vector (no shell). CancerJev generates a manifest, records
stdout/stderr and version, verifies GDC MD5 and size, computes SHA-256, and registers content-addressed
objects. Its transfer protocol is not reimplemented. Install the official executable from the
[GDC Data Transfer Tool page](https://gdc.cancer.gov/access-data/gdc-data-transfer-tool) and configure
its path. It is intentionally not redistributed in the image pending an explicit binary-distribution review.
