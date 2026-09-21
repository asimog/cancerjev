# CJ-R16 — Biomedical identifiers, Claims, and evidence core

**Status:** planned. **Owner:** evidence domain. **Depends on:** R11–R15.

## Mission

Represent biomedical entities and atomic claims with stable identity, provenance,
scope, and support/contradiction relationships.

## Implementation

Add versioned identifiers for genes, diseases, cohorts, alterations, interventions,
outcomes, publications, and methods. Define atomic Claim subject/predicate/object,
qualifiers, context, polarity, provenance, coverage, and status. Evidence references
immutable Findings, public literature records, or reviewed human evidence; aliases and
ambiguous mappings remain explicit. Corrections supersede rather than mutate.

## Open-data rule

Every evidence item records access class, acquisition mode, public source identity,
and coverage. A slice-derived Claim is constrained to registered regions and cannot
imply whole-assay absence.

## Tests and acceptance

Identifier normalization, collisions, aliases, ambiguity, atomicity, provenance,
support/contradiction, supersession, partial coverage, and controlled references are
tested. No Claim exists without an exact evidence boundary and stable identity.
