# Agent protocol boundary

The V1 agent transport is HTTPS, JSON, and OpenAPI. MCP and A2A can be adapters later but are not required to claim, heartbeat, release, or submit work.

An agent receives a signed Work Unit and compact evidence packet derived from a frozen snapshot. It returns a strict structured submission. It receives neither database credentials nor raw omics matrices, and CancerJev never executes contributor code.

