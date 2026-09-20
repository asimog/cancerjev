# Reviewed NCI-GDC upstreams

Reviewed 2026-09-20 using each repository's default-branch HEAD. CancerJev copies no upstream source.

| Repository | Default branch | Reviewed SHA | License | CancerJev use | Runtime dependency |
|---|---|---|---|---|---|
| NCI-GDC/gdc-client | develop | `048983310277463893b7ab4a153a190340ec8b8b` | Apache-2.0 | Official bulk transfer executable | External executable for materialization |
| NCI-GDC/gdcdictionary | develop | `88d66b0fe361aa638977850c180bd9130d705924` | Apache-2.0 | Semantic/schema reference | No |
| NCI-GDC/gdc-models | develop | `f568d785915761b9c5902f9ce4d05e4aa9bbb11c` | Apache-2.0 | Identity/entity relationship reference | No |
| NCI-GDC/gdc-workflow-overview | master | `2412e93b3d7de8afb74ad6e28566e5a6b2e0ad1e` | Apache-2.0 | Harmonization/provenance reference | No |
| NCI-GDC/gdc-rnaseq-cwl | master | `05460f7dfca5a900d7635ccae0e1b28cf764a02f` | Apache-2.0 | RNA processing provenance; never rerun by CancerJev | No |
| NCI-GDC/gdc-dnaseq-cwl | master | `ed98a652e8196296dc3cac7db2e1fa5723d237b4` | Apache-2.0 | DNA processing provenance; never rerun by CancerJev | No |
| NCI-GDC/gdc-frontend-framework | develop | `de23d8a9d2c3416217badedb89476b98c70ce916` | Apache-2.0 | UI patterns reviewed; portal not forked | No |

The APIs remain the live source for open metadata. Version records are references, not claims that CancerJev reproduces GDC harmonization.
