# Open-data policy

CancerJev V1 processes public GDC data only.

1. File discovery always combines the requested project with `files.access = open`.
2. Callers cannot supply or override the access filter.
3. Snapshot creation validates every returned object and fails closed if any object is not open.
4. The service has no GDC token setting and accepts no dbGaP or eRA Commons credentials.
5. Controlled file identifiers must not be placed in work units, evidence packets, logs, or fixtures.

This boundary must be reviewed before any controlled-data phase is designed.

