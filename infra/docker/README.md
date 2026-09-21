# Docker infrastructure

The root `compose.yaml` is a development topology for API, web, ingest/statistics
workers, PostgreSQL, MinIO, migrations, and bucket initialization. It is not a
production architecture.

At the restored baseline, build contexts lack exclusions and host ports are fixed;
CJ-R00 must add `.dockerignore`, reproducible installs, health/startup proof, and
configurable bindings. Local credentials are disposable development values. GDC
credentials are prohibited. CJ-R33 owns production deployment and recovery.
