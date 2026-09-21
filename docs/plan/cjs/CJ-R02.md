# CJ-R02 — Complete open-data snapshot identity

**Status:** planned. **Owner:** `packages/gdc` snapshot identity; resources register;
storage owns bytes. **Depends on:** R00–R01.

## Mission and baseline

Make a snapshot a complete, versioned identity of the public cohort selection. R00
introduces identity v2 and conflict rejection; R02 completes selection authority,
upstream provenance, compatibility, and publication threat handling.

## Implementation

- Hash normalized case, sample, aliquot, file, workflow, access, status, relationship,
  requested-field, schema, mapping, selection, and source-policy records.
- Separate identity-bearing fields from informational acquisition timestamps.
- Reject conflicting duplicates before canonical sorting and hashing.
- Verify existing local/S3 objects before idempotent reuse and keep v1 readable.
- Publish identity, manifest, coverage, and provenance atomically with one digest map.

## Open-data rule

Every returned file must be exactly `access=open`. Missing, unknown, controlled, or
mixed access aborts before hashing and publication. Only the official GDC host is an
upstream authority; no authentication field exists.

## Tests and acceptance

Order changes preserve identity; any identity-bearing change alters it; conflicts,
source changes, status drift, corrupt existing objects, symlink/path escape, and
non-open hits fail closed. A published v2 snapshot is metadata-complete and backed by
verified immutable bytes. Acquisition orchestration remains R04.
