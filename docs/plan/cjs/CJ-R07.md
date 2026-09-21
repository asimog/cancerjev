# CJ-R07 — Public-data validation firewall

**Status:** planned. **Owner/data:** partition service owns immutable assignments;
validation service owns reveal policy. **Depends on:** R02, R06.

## Mission

Partition explicitly public data into discovery and hidden validation sets while
preventing scientific leakage before hypothesis lock.

## Implementation

- Create deterministic, versioned case-level partition assignments using frozen
  biological lineage; related samples/aliquots cannot cross partitions.
- Store assignment hash and policy, with restricted validation membership/output
  views enforced in services, SQL, API, exports, logs, metrics, and error messages.
- Permit validation execution only from an immutable HypothesisLock in R24.
- Make contamination detection and invalidation explicit.

## Open-data rule

Both partitions contain public data only. The firewall protects confirmatory validity,
not legal access, and it never creates permission to acquire restricted data.

## Tests and acceptance

Determinism, balance, lineage grouping, cross-project isolation, enumeration,
timing/error leakage, export/log leakage, and early reveal are tested. Discovery code
cannot query validation membership or outcomes before a valid locked execution.
