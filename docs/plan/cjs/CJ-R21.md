# CJ-R21 — Reproducible Evidence Graph

**Status:** planned. **Owner/data:** evidence graph service and generation records.
**Depends on:** R16–R20.

## Mission

Create a queryable, rebuildable graph connecting entities, Claims, Findings,
literature, methods, evaluations, hypotheses, and validation outcomes.

## Implementation

Define typed node/edge schemas, direction, provenance, polarity, temporal validity,
generation identity, graph invariants, supersession, and deterministic projection from
source ledgers. Store authoritative records outside the graph projection; rebuilds
must not depend on traversal order. Expose bounded project-authorized queries.

## Open-data rule

Every evidence node/edge preserves public-access and coverage scope. Graph inference
cannot merge regional evidence with whole-assay evidence or inaccessible references
as equivalent support.

## Tests and acceptance

Dangling/cyclic-invalid edges, duplicate identities, support/contradiction,
supersession, deterministic rebuild, project isolation, partial coverage, and lineage
queries are tested. Every displayed conclusion traces to immutable source evidence.
