# CJ-R20 — Native in-process research agent

**Status:** planned. **Owner:** native AgentRuntime. **Depends on:** R17–R19.

## Mission

Run the first complete research agent inside CancerJev using shared contracts and
without network/distributed complexity.

## Implementation

Implement deterministic runtime orchestration around a bounded reasoning provider:
consume EvidencePacket, produce structured competing mechanisms, predictions,
falsifiers, experiment proposals, literature needs, and next-action suggestions;
validate Submission; record prompts/state/model/usage/budgets in the Reasoning Ledger.
Provider prose remains untrusted until validation.

## Open-data rule

The agent cannot request credentials, controlled data, full BAMs, arbitrary regions,
or bypass URLs. Needs not answerable from allowed public operations become explicit
non-executable external research needs.

## Tests and acceptance

Deterministic fake-provider scenarios, malformed answers, timeouts, retries, budgets,
prompt injection, stale evidence, unsupported claims, and inaccessible-data requests
are tested. A valid native WorkUnit produces one validated Submission with complete
ledger provenance and no scientific-status mutation.
