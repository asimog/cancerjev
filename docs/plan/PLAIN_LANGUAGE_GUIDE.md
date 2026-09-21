# CancerJev Roadmap in Plain Language

CancerJev never asks for a GDC token or uses restricted patient data. It tries
metadata first, then a small public processed file, then a bounded slice of an
explicitly open BAM, and only then another bounded public-file transfer. A slice is
partial evidence; everything outside it is not examined.

| CJ | What it means | How users know it works |
| --- | --- | --- |
| R00 | Repair today’s foundation before adding features. | Packaging, jobs, identities, CI, security scans, and full local stack all pass. |
| R01 | Make every checkout build and test the same way. | One documented command set passes noninteractively and rejects GDC credential paths. |
| R02 | Freeze the complete identity of every public dataset. | Any non-open or conflicting record stops snapshot publication. |
| R03 | Prevent crashed or stale workers from publishing. | One fenced attempt wins; access failures stop permanently. |
| R04 | Acquire only the smallest public evidence needed. | Full BAMs, tokens, unknown access, and unbounded slices are rejected. |
| R05 | Run science only from frozen artifacts. | No analysis contacts live GDC; whole-assay engines reject slices. |
| R06 | Protect CancerJev projects without unlocking GDC. | Users see project permissions and no GDC-token setting. |
| R07 | Keep public validation data hidden until a plan is locked. | Discovery cannot inspect validation membership or outcomes early. |
| R08 | Build trustworthy public mutation, CNV, and RNA summaries. | Missing or unexamined data never appears negative. |
| R09 | Compare modalities while respecting covariates and coverage. | Results list the exact tested features, samples, and adjustments. |
| R10 | Make survival endpoints and censoring explicit. | Reports show public fields used and never infer unavailable variables. |
| R11 | Make Findings immutable and reproducible. | Exact stored artifacts reproduce the same identity without live authenticated data. |
| R12 | Record every search and its multiple-testing universe. | Regional searches cannot claim genome-wide testing. |
| R13 | Put all Jev calls behind one audited service. | Jev receives compact summaries, never credentials, raw BAMs, or scientific authority. |
| R14 | Tell Jev exactly what evidence and coverage exist. | Jev cannot infer missing or controlled data. |
| R15 | Allow only budgeted, registered follow-up analyses. | The loop stops at data, region, byte, time, and iteration limits. |
| R16 | Normalize biomedical entities and atomic Claims. | Each Claim retains public source and coverage scope. |
| R17 | Give every research component the same safe contracts. | EvidencePackets contain bounded evidence, not raw BAMs or bypass URLs. |
| R18 | Verify public literature and what was actually read. | Paywalled text is not bypassed or described as reviewed. |
| R19 | Reject unsafe or unsupported submissions centrally. | Bad provenance and slice overclaims stop before Jev/evaluation. |
| R20 | Run the first research agent inside CancerJev. | Unsupported data needs become non-executable research needs. |
| R21 | Trace conclusions through a typed Evidence Graph. | Regional and whole-assay evidence cannot be merged as equivalent. |
| R22 | Distinguish known, unknown, not acquired, and unavailable. | Users see precise ResearchState labels with evidence-backed transitions. |
| R23 | Turn approved intentions into safe WorkUnits. | No authenticated-GDC action exists in the registry. |
| R24 | Lock hypotheses before revealing validation. | The locked digest blocks retrospective changes and restricted-data substitution. |
| R25 | Prove the entire native loop. | Positive public fixtures pass and every forbidden data path fails safely. |
| R26 | Give researchers a complete cockpit. | Access, coverage, provenance, limits, and status appear beside every result. |
| R27 | Export exact handoffs and import reviewed evidence. | Packages retain checksums, examined regions, and unavailable-data limits. |
| R28 | Benchmark agents on real safety and evidence behavior. | Agents that fabricate from inaccessible data are ineligible. |
| R29 | Replicate bounded work across suitable agents. | Replicas receive identical EvidencePackets and no broader access. |
| R30 | Add external contributors only as an opt-in adapter. | Default deployments expose no external workflow or GDC credential route. |
| R31 | Treat agreement as reasoning, not new evidence. | Consensus preserves missingness, access, and coverage limitations. |
| R32 | Attack and load-test the distributed boundary. | Smuggled auth, controlled UUIDs, raw BAMs, and fabricated coverage are blocked. |
| R33 | Prove production can operate and recover safely. | Live release evidence shows public-only minimal acquisition, restore, and no credentials. |

Each row is only a summary. The matching file in [`cjs/`](cjs/README.md) defines the
tests and acceptance criteria.
