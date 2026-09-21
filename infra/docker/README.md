# Docker infrastructure

The root `compose.yaml` is a development topology for API, web, ingest/statistics
workers, PostgreSQL, MinIO, migrations, and bucket initialization. It is not a
production architecture.

CJ-R00 added root/web build-context exclusions, lockfile-based frontend installation,
provider-independent health checks, and configurable loopback host bindings. Override
`CANCERJEV_API_PORT`, `CANCERJEV_WEB_PORT`, `CANCERJEV_MINIO_PORT`, and
`CANCERJEV_MINIO_CONSOLE_PORT` for concurrent project names, then run
`python scripts/compose_smoke.py --project NAME`.

Local credentials are disposable development values. GDC credentials are prohibited.
CJ-R33 owns production deployment and recovery; this topology is not production.
