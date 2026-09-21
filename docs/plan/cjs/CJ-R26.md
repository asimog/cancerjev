# CJ-R26 — Researcher cockpit

**Status:** planned. **Owner:** web/API presentation boundaries. **Depends on:** R25.

## Mission

Give researchers a complete, accessible interface to projects, public datasets,
acquisition, runs, candidates, evidence, Jev reasoning, validation, reproduction, and
handoff without making the UI an authority.

## Implementation

Build project dashboard, dataset/snapshot browser, acquisition preview, job timeline,
analysis/search explorer, candidate/evidence graph, Finding/reproduction, hypothesis
lock/validation, budgets, audit, and export screens. APIs return typed read models;
long work is asynchronous; errors and provenance are actionable. Enforce R06 access
at APIs and downloads. Add accessibility and responsive/browser coverage.

## Open-data rule

Display `public`, `complete processed artifact`, `bounded slice`, `region not
examined`, `unavailable controlled`, and `no public source` beside affected results.
Never show not examined as negative or offer a GDC-token/full-BAM control.

## Tests and acceptance

Browser tests cover every state, loading/error/retry, project isolation, keyboard and
screen-reader semantics, exports, stale updates, and mobile layouts. The CJ-R25 journey
is understandable and operable entirely through supported UI/API flows.
