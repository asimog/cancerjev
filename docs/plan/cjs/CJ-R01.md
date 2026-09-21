# CJ-R01 — Reproducible packaging and CI

**Status:** planned after R00. **Owner:** build, CI, and repository tooling.

## Mission and baseline

Make clean checkout, wheel, frontend, images, migrations, and Compose reproducible.
R00 must already have repaired the missing `scientific` wheel package and interactive
lint; R01 turns those repairs into protected, documented release gates.

## Implementation

- Pin supported Python/Node/database versions and lock dependency resolution.
- Run Ruff, full PostgreSQL tests, isolated wheel imports, frontend lint/typecheck/
  build, migration validation, image builds, and Compose smoke in CI.
- Add dependency, license, secret, forbidden-GDC-auth, and documentation-link scans.
- Minimize build contexts and publish bounded test evidence/artifacts.
- Define required checks for main and a versioned release evidence manifest.

## Open-data rule

CI fails if configuration, schemas, environment names, database columns, client code,
deployment secrets, or GDC adapters create token, cookie, authenticated-transfer,
controlled-data, full-BAM, or unbounded-slice capabilities.

## Tests and acceptance

Fresh locked installs pass on supported versions; the wheel works outside the source
tree; all gates are noninteractive; intentionally adding `X-Auth-Token` or a GDC
token setting fails policy scanning; ordinary CancerJev login and object-storage
credentials remain distinguishable. No scientific or product feature is added.

**Done:** required main checks are enforced, repeatable, documented, and green.
