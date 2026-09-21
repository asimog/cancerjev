# CJ-R28 — Hidden benchmarks and capability profiles

**Status:** planned. **Owner:** benchmark service. **Depends on:** R19, R25.

## Mission

Measure agent capabilities and safety on hidden versioned tasks before scheduling
real research work.

## Implementation

Define benchmark suites, sealed fixtures, scoring, reproducibility, contamination
detection, profile version/expiry, minimum thresholds, and auditable runs. Measure
contract compliance, claim grounding, citation verification, uncertainty, diversity,
coverage reasoning, refusal behavior, and resource use. Publish only scheduling-safe
profile summaries, not hidden answers.

## Open-data rule

Benchmarks explicitly test refusal of credentials/controlled data/full BAMs and
correct handling of missing, inaccessible, and regional evidence. Fabrication from
unavailable data is disqualifying.

## Tests and acceptance

Stable scoring, fixture secrecy, reruns, leakage invalidation, adversarial prompts,
profile expiry, version incompatibility, and threshold enforcement pass. An unsafe or
unbenchmarked agent cannot receive matching WorkUnits.
