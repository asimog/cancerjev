# CancerJev Canonical Implementation Roadmap

Baseline: restored `origin/main` at `2bf6c68d93741b9974f46983e0a35c691d69c1f1`.
Status: CJ-R00 completed and verified on 2026-09-22; CJ-R01 is next. CJ-R01–CJ-R33
remain planned and have not begun.

Every row links to its authoritative, separately reviewable specification. Later CJs
may refine files and symbols after predecessors land, but may not weaken open-data,
scientific-authority, provenance, or validation invariants.

| CJ | Milestone | Outcome | Depends on |
| --- | --- | --- | --- |
| [R00](cjs/CJ-R00.md) | Gate 0 | Baseline audit repairs and readiness proof | restored main |
| [R01](cjs/CJ-R01.md) | A | Reproducible packaging and CI | R00 |
| [R02](cjs/CJ-R02.md) | A | Complete open-data snapshot identity | R00–R01 |
| [R03](cjs/CJ-R03.md) | A | Lease fencing and terminal recovery | R00–R02 |
| [R04](cjs/CJ-R04.md) | A | Minimal public acquisition and bounded BAM slicing | R02–R03 |
| [R05](cjs/CJ-R05.md) | A | Artifact-only scientific execution | R00, R02–R04 |
| [R06](cjs/CJ-R06.md) | A | Runtime isolation, project boundaries, quotas, service scopes | R01, R03, R05 |
| [R07](cjs/CJ-R07.md) | A | Hidden public-data validation firewall | R02, R06 |
| [R08](cjs/CJ-R08.md) | A | Public mutation, CNV, and RNA summaries | R04–R07 |
| [R09](cjs/CJ-R09.md) | B | Cross-modal and covariate-aware engines | R08 |
| [R10](cjs/CJ-R10.md) | B | Versioned survival methods | R05–R09 |
| [R11](cjs/CJ-R11.md) | B | Immutable Findings and reproduction | R05, R08–R10 |
| [R12](cjs/CJ-R12.md) | B | SearchRun, deterministic candidate gate, and CandidateObservation | R08–R11 |
| [R13](cjs/CJ-R13.md) | B | JevService and Semantic Ledger | R01, R06, R12 |
| [R14](cjs/CJ-R14.md) | B | CandidateState and explicit Jev modes | R12–R13 |
| [R15](cjs/CJ-R15.md) | B | Budgeted adaptive discovery | R12–R14 |
| [R16](cjs/CJ-R16.md) | C | Biomedical identifiers, Claims, evidence | R11–R15 |
| [R17](cjs/CJ-R17.md) | C | Shared research work contracts | R16 |
| [R18](cjs/CJ-R18.md) | C | Verified public literature retrieval | R16–R17 |
| [R19](cjs/CJ-R19.md) | C | Canonical Submission validation | R16–R18 |
| [R20](cjs/CJ-R20.md) | C | Native in-process research agent | R17–R19 |
| [R21](cjs/CJ-R21.md) | C | Reproducible Evidence Graph | R16–R20 |
| [R22](cjs/CJ-R22.md) | C | Scientific synthesis and ResearchState | R21 |
| [R23](cjs/CJ-R23.md) | C | ResearchAction and WorkUnitFactory | R17, R22 |
| [R24](cjs/CJ-R24.md) | C | HypothesisLock and validation execution | R07, R11, R21–R23 |
| [R25](cjs/CJ-R25.md) | C | Native full-loop acceptance | R01–R24 |
| [R26](cjs/CJ-R26.md) | D | Researcher cockpit consolidation and hardening | R25 |
| [R27](cjs/CJ-R27.md) | D | Research handoff and reviewed intake | R16, R21, R25–R26 |
| [R28](cjs/CJ-R28.md) | E | Hidden benchmarks and capability profiles (optional) | R19, R25 |
| [R29](cjs/CJ-R29.md) | E | Replicated scheduler and diversity (optional) | R17, R25, R28 |
| [R30](cjs/CJ-R30.md) | E | Disabled external contributor API/client (optional) | R19, R25, R28–R29 |
| [R31](cjs/CJ-R31.md) | E | Convergence and adaptive allocation (optional) | R21–R23, R29–R30 |
| [R32](cjs/CJ-R32.md) | E | Distributed security/load/failure acceptance (optional) | R28–R31 |
| [R33](cjs/CJ-R33.md) | F | Deployment, observability, recovery, release | R01–R27 (native); R28–R32 only for distributed-enabled releases |

Milestone E (R28–R32) is an optional distributed-contributor program. Native
production readiness (R33) does not depend on it; when distributed execution is
enabled, R33 additionally requires the CJ-R32 distributed-release acceptance.

## Discovery model

Broad discovery is deterministic. A SearchRun executes one registered method/version
over one frozen cohort and tested universe; complete result sets stay in immutable
artifacts while the method-specific deterministic candidate gate turns only qualifying
results into CandidateObservations. Jev then judges the compact CandidateState
shortlist, and later generative reasoning remains CJ-R20. The V1 families (D01–D09) and
their minimum method contracts are defined once in the
[V1 discovery catalogue](../scientific/discovery-catalogue-v1.md). Thin functional
research surfaces accompany R05, R08–R10, R12–R15, and R24; R26 consolidates them into
the complete cockpit.

## Global definition of done

Every CJ must preserve ownership, add migrations only when required, use explicit
versioned contracts, test success/failure/boundary behavior, run relevant PostgreSQL
and browser/worker integration, review its diff, update architecture/current docs,
and leave no credential or uncontrolled data-transfer path.

Every CJ must include an explicit public-data test. GDC records not exactly
`access=open`, any GDC authentication material, complete BAM requests, and unbounded
slices fail before network transfer. Slice-derived conclusions remain regional.
