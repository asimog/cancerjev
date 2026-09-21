# CJ-R33 — Deployment, observability, recovery, and release gate

**Status:** planned final gate. **Owner:** platform operations with domain-owner
sign-off. **Depends on:** R01–R32.

## Mission

Release a recoverable production system with evidence that scientific, public-data,
security, and user-journey invariants survive the real deployment topology.

## Implementation

Define environments, infrastructure contracts, secret matrix, migration strategy,
worker scaling, object lifecycle, backups, point-in-time recovery, disaster recovery,
health/readiness, structured redacted telemetry, SLOs, alerts, runbooks, incident
process, rollback, dependency inventories, SBOM/signing, and release evidence. Restore
PostgreSQL and CAS together and verify cross-store references before reopening writes.

## Open-data rule

The production secret matrix contains no GDC credential. Release scanning covers
configuration, environment variables, request models, schemas, clients, databases,
object storage, logs, and docs. Only official GDC, explicit open files,
metadata-first bounded acquisition, optional unauthenticated open-parent slicing, and
terminal authorization failure are permitted; full BAM is disabled.

## Tests and acceptance

Run clean deployment, migration, rollback, backup/restore, corruption, region/service
failure, worker death, scaling, load, alert, browser/API/worker journey, and policy
negative tests. The live acceptance proves no credential appears anywhere, one native
public-data research loop completes reproducibly, unavailable/not-examined labels are
truthful, recovery meets objectives, and release evidence is signed and archived.
