# ADR-001 — Durable resource ownership

**Status:** accepted; current.

## Context

Snapshots, artifacts, materializations, cohorts, analyses, Findings, audit events,
and jobs require transactional identity and cannot be owned by request handlers or
filesystem conventions.

## Decision

PostgreSQL stores authoritative resource metadata. `packages/resources` owns
application transactions and invariants through repository contracts implemented by
`packages/database`. Immutable bytes live in a content-addressed object store. API and
workers call resource services rather than mutating tables directly. Large scientific
data belongs in artifacts, never JSON job/resource payloads.

Jobs are durable records with attempts and leases. CJ-R00 and R03 complete fencing
and recovery. Scientific resources are immutable after publication; correction uses
new resources and explicit supersession/retraction.

## Consequences

The database and CAS must be backed up/restored coherently. New modules do not share
table mutation ownership. Migrations protect critical invariants independently of the
API. SQLite is not a supported substitute for PostgreSQL behavior.
