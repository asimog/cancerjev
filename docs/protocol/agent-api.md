# Agent protocol boundary

External agent transport is not implemented and remains disabled through CJ-R29.
Native execution in CJ-R20 must first prove the shared contracts and CJ-R25 must prove
the complete loop.

The future boundary uses versioned WorkUnit, EvidencePacket, Submission, Evaluation,
capability, budget, error, and result contracts owned by CancerJev. Contributors do
not receive database access, object-store credentials, raw BAMs, genomic matrices,
GDC credentials, controlled UUIDs, arbitrary URLs, or permission to widen evidence.

CJ-R30 defines transport/authentication; R32 defines adversarial and load acceptance.
Contributor keys authenticate only to CancerJev and never authorize GDC requests.
