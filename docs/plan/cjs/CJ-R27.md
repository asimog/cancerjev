# CJ-R27 — Research handoff and reviewed result intake

**Status:** planned. **Owner:** handoff service and reviewed-evidence intake.
**Depends on:** R16, R21, R25–R26.

## Mission

Export exact research packages for human/wet-lab work and safely re-enter reviewed
results without conflating external evidence with native deterministic Findings.

## Implementation

Define signed/versioned handoff manifests containing question, Claims, evidence,
methods, inputs, hashes, coverage, limitations, predictions, falsifiers, requested
experiment, expected result schema, and review instructions. Intake validates package
identity, reviewer attribution, schema, attachments, checksums, provenance, and
conflicts; accepted items enter reviewed evidence with an audit trail.

## Open-data rule

State the exact public evidence boundary and unavailable controlled-data needs.
Slice-derived handoffs list genes/coordinates and limitations. CancerJev does not
recommend obtaining restricted data or ingest raw BAM uploads.

## Tests and acceptance

Round trip, tamper, version mismatch, duplicate intake, malicious attachment,
cross-project access, partial coverage, controlled reference, and supersession tests
pass. External reviewed evidence remains visibly distinct and traceable.
