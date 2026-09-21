# Open-data policy

This policy is non-negotiable for CJ-R00–CJ-R33.

1. CancerJev uses only freely and anonymously available public data.
2. Every GDC file must explicitly state `access=open`.
3. Missing, unknown, restricted, or controlled access fails closed.
4. The only production GDC authority is `https://api.gdc.cancer.gov`.
5. CancerJev never accepts, stores, configures, transmits, or requests GDC tokens,
   `X-Auth-Token`, GDC `Authorization`, cookies, token files, dbGaP credentials, or
   transfer-tool token options.
6. CancerJev application identity protects CancerJev resources only and cannot unlock
   GDC data.
7. Acquisition uses this priority:

   ```text
   metadata
     -> minimal processed open file
     -> bounded open BAM slice
     -> bounded public-file transfer
   ```

8. V1 prohibits full BAM downloads, whole chromosomes, open-ended ranges, unmapped
   reads, empty/arbitrary regions, and unbounded slice requests.
9. A slice is partial evidence. Outside its registered genes/closed coordinates, the
   state is `NOT_EXAMINED`, never negative.
10. A GDC authorization response is terminal `UNAVAILABLE_ACCESS`; no authenticated
    retry or credential-seeking action is allowed.

Any proposal to support controlled data requires explicit replacement of the product
mission, architecture, threat model, and this policy. It cannot be added by an
ordinary CJ or configuration flag.
