# Agent protocol boundary

The V1 agent transport is HTTPS, JSON, and OpenAPI. MCP and A2A can be adapters later but are not required to claim, heartbeat, release, or submit work.

An agent receives a signed Work Unit and compact evidence packet derived from a frozen snapshot. It returns a strict structured submission. It receives neither database credentials nor raw omics matrices, and CancerJev never executes contributor code.

## Model provider boundaries

Generative agent work and Jev decisions are different protocols and use independent base URLs,
API keys, and model identifiers. The generative boundary is OpenRouter-compatible
`/chat/completions`. Jev follows TypeSafe's `POST /v1/systemone` contract: shared `state`, a map
of typed Choice/Score/Noul `questions`, and structured `answers` under the same question IDs.

CancerJev exposes `POST /v1/jev/evaluate` for typed evaluation and
`POST /v1/jev/evidence-judgments` for the versioned canonical evidence relationship question.
The latter is always a three-way Choice: `SUPPORT`, `CONTRADICT`, or `UNRESOLVED`. The returned
confidence and distribution are model routing signals; they are not evidence, replication, or
a probability that a mechanism is biologically true. If Jev is unconfigured or unavailable,
deterministic ingestion remains operational and the judgment must remain pending.
