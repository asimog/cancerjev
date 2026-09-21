# CJ-R18 — Verified public literature retrieval

**Status:** planned. **Owner:** literature adapter plus evidence service.
**Depends on:** R16–R17.

## Mission

Retrieve lawful public literature metadata/content and verify that cited evidence
exists and supports the represented claim relationship.

## Implementation

Use stable publication identifiers, source/type, retrieval timestamp, content hash,
license/access label, exact excerpt location, and retraction/correction status. Fetch
bounded metadata, abstracts, and open full text through allowlisted adapters. Separate
retrieval from claim-relation classification; cache immutable source artifacts and
record unavailable states.

## Open-data rule

Do not bypass paywalls, sessions, private repositories, or authenticated full text.
Paid/private content is unavailable unless a separately reviewed lawful human-evidence
process supplies provenance; that process cannot authorize GDC data.

## Tests and acceptance

Known identifiers, redirects, retractions, duplicate versions, malformed content,
unsupported citations, access denial, size limits, and cache replay are tested.
CancerJev never claims to have read content it did not lawfully retrieve.
