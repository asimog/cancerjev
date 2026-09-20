# NCI-GDC upstream adoption record

CancerJev consumes selected NCI-GDC projects and patterns without forking the GDC portal. This keeps ownership boundaries clear and avoids silently diverging from upstream scientific processing.

| Upstream | CancerJev use | Integration choice |
|---|---|---|
| [`NCI-GDC/gdc-client`](https://github.com/NCI-GDC/gdc-client) | Large manifest-based transfers, retries, and resume | Official external executable; do not reimplement transfer |
| [`NCI-GDC/gdc-frontend-framework`](https://github.com/NCI-GDC/gdc-frontend-framework) | UX and reusable scientific-visualization reference | Study/adapt patterns; do not fork the whole portal |
| [`NCI-GDC/gdcdictionary`](https://github.com/NCI-GDC/gdcdictionary) | Data definitions and field semantics | Versioned schema reference behind our canonical model |
| [`NCI-GDC/gdc-models`](https://github.com/NCI-GDC/gdc-models) | Case/biospecimen/sample/file graph semantics | Mapping reference; no direct domain leakage |
| [`NCI-GDC/gdc-workflow-overview`](https://github.com/NCI-GDC/gdc-workflow-overview) | Harmonization provenance and processing assumptions | Documentation/reference only in V1 |
| [`NCI-GDC/gdc-rnaseq-cwl`](https://github.com/NCI-GDC/gdc-rnaseq-cwl) | RNA-seq workflow provenance | Record upstream workflow/version; do not rerun harmonization |
| [`NCI-GDC/gdc-dnaseq-cwl`](https://github.com/NCI-GDC/gdc-dnaseq-cwl) | DNA-seq workflow provenance | Record upstream workflow/version; do not rerun harmonization |

The initial scaffold pins the upstream revisions reviewed when this record was created:

```text
gdc-client:             048983310277463893b7ab4a153a190340ec8b8b
gdc-frontend-framework: de23d8a9d2c3416217badedb89476b98c70ce916
```

These are provenance references, not Git submodules. Build/runtime code uses the public GDC REST API and an operator-provided official `gdc-client` binary. Any future copied code must retain its upstream license and be documented in `NOTICE` before merge.

