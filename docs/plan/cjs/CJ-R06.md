# CJ-R06 — Runtime isolation, project boundaries, quotas, and service scopes

**Status:** planned. **Owner:** runtime boundary and resource services own project
isolation and quotas. **Depends on:** R01, R03, R05.

## Mission

Protect CancerJev projects, jobs, and results through runtime isolation, budgets, and
service-level access rules — without end-user login and without confusing CancerJev
service credentials with GDC data authorization.

CancerJev does not require end-user accounts, passwords, sessions, user roles, or user
membership. If a future approved product decision adds end-user identity, it requires a
new CJ and architecture change, not an extension of this milestone.

## Implementation

- Add project/resource isolation: object-key, job, export, and query boundaries that
  prevent cross-project disclosure, including timing and error-message channels.
- Add service-level authorization for deployment/API service credentials where the
  deployment requires them; enforce in API/application services and worker-created
  operations, never via UI hiding or CORS.
- Add per-project acquisition, compute, storage, semantic, and concurrency quotas with
  atomic accounting, concurrency limits, and stable rejection codes.
- Record quota consumption, rejections, and boundary decisions as audit events.

## Open-data rule

No service credential, scope, or quota may unlock controlled GDC data, accept a GDC
token, proxy an authenticated GDC request, or override OpenDataPolicy. CancerJev
service credentials are valid only for CancerJev-owned resources and can never
authorize GDC data access.

## Tests and acceptance

Isolation, boundary, quota, race, object-download, and rejection-code cases are
covered in API/browser/PostgreSQL tests. A fully privileged CancerJev service context
still receives `UNAVAILABLE_ACCESS` for controlled GDC data, and no test requires an
end-user account to exist.
