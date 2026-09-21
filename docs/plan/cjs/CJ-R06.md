# CJ-R06 — Application identity, authorization, quotas, and scopes

**Status:** planned. **Owner:** application identity boundary; resources own project
membership and quotas. **Depends on:** R01, R03, R05.

## Mission

Protect CancerJev users, projects, jobs, and results without confusing application
authentication with GDC data authorization.

## Implementation

- Add provider-neutral user/session identity, project membership, roles, scopes,
  service credentials, revocation, and audit events.
- Enforce authorization in API/application services and worker-created operations;
  never rely on UI hiding or CORS.
- Add per-user/project acquisition, compute, storage, semantic, and concurrency
  quotas with atomic accounting and stable rejection codes.
- Prevent object-key, job-ID, export, and timing-based cross-project disclosure.

## Open-data rule

No role or scope may unlock controlled GDC data, accept a GDC token, proxy an
authenticated GDC request, or override OpenDataPolicy. Product sessions and
contributor keys are valid only for CancerJev-owned resources.

## Tests and acceptance

Anonymous, member, researcher, administrator, revoked, expired, cross-project, quota,
race, and object-download cases are covered in API/browser/PostgreSQL tests. A fully
privileged CancerJev user still receives `UNAVAILABLE_ACCESS` for controlled GDC data.
