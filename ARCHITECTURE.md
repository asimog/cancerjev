# CancerJev architecture map

CancerJev keeps scientific bytes separate from durable resource metadata.

| Owner | Responsibility and state |
| --- | --- |
| `packages/gdc` | Official GDC metadata adapter, frozen identity resolution, versioned format parsing, local normalization, verified canonicalization |
| `packages/schemas` | Strict identity, snapshot, molecular v2, and compact job contracts |
| `packages/storage` | Atomic immutable snapshots, content-addressed File/S3 objects, Parquet storage |
| `packages/resources` | Transactional resource operations and source/materialization orchestration |
| `packages/database` | PostgreSQL metadata, jobs, immutable artifact and lineage records, SQL repositories |
| `workers/ingest` | Resolve compact durable job identities and invoke application operations |
| `packages/statistics`, `workers/statistics` | Existing scientific primitives; artifact-backed discovery integration remains a later stage |
| `apps/api` | Validate requests and expose resource services |

Workers depend on application services; services use repository and storage contracts.
GDC format parsers depend on canonical schemas and frozen identity records, not on PostgreSQL
or vendor storage SDKs. PostgreSQL owns metadata and lifecycle; object storage owns immutable
source/Parquet bytes. Frozen snapshots remain authoritative for molecular identity.

See [resource architecture](docs/architecture/resources.md) for transactions and persistence,
[data foundation](docs/architecture/data-foundation.md) for snapshot invariants, and
[GDC materialization](docs/architecture/gdc-materialization.md) for parser contracts and limits.
