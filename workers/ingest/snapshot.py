from typing import Any, Protocol

from packages.gdc.coverage import build_coverage
from packages.gdc.filters import open_project_files
from packages.gdc.manifest import generate_manifest
from packages.gdc.mappings import map_file_hit
from packages.provenance.hashing import canonical_hash
from packages.schemas.snapshot import LogicalSnapshotRequest, SnapshotObject, SnapshotRecord


class SnapshotRepository(Protocol):
    def save(self, snapshot: SnapshotRecord) -> Any: ...


class LogicalSnapshotService:
    def __init__(self, *, client: Any, repository: SnapshotRepository):
        self.client = client
        self.repository = repository

    async def create(self, request: LogicalSnapshotRequest) -> SnapshotRecord:
        payload = await self.client.get_open_files(request.project_id)
        hits = payload.get("data", {}).get("hits", [])
        # Raw GDC hits deliberately never cross the canonical boundary.  GDC adds
        # requested/nested fields over time, while SnapshotObject remains strict.
        objects = tuple(sorted((map_snapshot_object(hit) for hit in hits), key=lambda x: x.file_id))
        if any(item.access != "open" for item in objects):
            raise ValueError("GDC returned a controlled file for an open-data snapshot")

        query = open_project_files(request.project_id)
        mapped = [map_file_hit(hit) for hit in hits]
        files = [item[0] for item in mapped]

        def unique(index: int, key: str) -> list:
            values = [value for item in mapped for value in item[index]]
            return sorted(
                {getattr(value, key): value for value in values}.values(),
                key=lambda value: getattr(value, key),
            )

        cases, samples = unique(1, "case_id"), unique(2, "sample_id")
        aliquots, links = unique(3, "aliquot_id"), unique(4, "file_id")
        # Links can share file IDs; de-duplicate on the full identity instead.
        links = sorted(
            {
                (v.file_id, v.case_id, v.sample_id, v.aliquot_id): v
                for item in mapped
                for v in item[4]
            }.values(),
            key=lambda v: (v.file_id, v.case_id, v.sample_id or "", v.aliquot_id or ""),
        )
        identity = {
            "project_id": request.project_id,
            "gdc_release": request.gdc_release,
            "query": query,
            "transformation_version": request.transformation_version,
            "objects": [item.model_dump(mode="json") for item in objects],
            "case_ids": [item.case_id for item in cases],
            "sample_ids": [item.sample_id for item in samples],
            "aliquot_ids": [item.aliquot_id for item in aliquots],
        }
        digest = canonical_hash(identity)
        snapshot = SnapshotRecord(
            snapshot_id=f"DS-{request.project_id}-{digest.removeprefix('sha256:')[:12]}",
            snapshot_hash=digest,
            project_id=request.project_id,
            source_api=self.client.base_url,
            gdc_release=request.gdc_release,
            query=query,
            transformation_version=request.transformation_version,
            objects=objects,
            case_ids=tuple(identity["case_ids"]),
            sample_ids=tuple(identity["sample_ids"]),
            aliquot_ids=tuple(identity["aliquot_ids"]),
        )
        location = self.repository.save(snapshot)
        root = location.parent
        (root / "manifest.tsv").write_bytes(generate_manifest(files))
        from packages.storage.parquet import write_records

        write_records(cases, root / "cases.parquet")
        write_records(samples, root / "samples.parquet")
        write_records(
            aliquots or [{"aliquot_id": None, "sample_id": None, "submitter_id": None}],
            root / "aliquots.parquet",
        )
        write_records(files, root / "files.parquet")
        write_records(links, root / "file_sample_links.parquet")
        write_records(build_coverage(cases, files, links), root / "coverage.parquet")
        import json

        (root / "provenance.json").write_text(
            json.dumps(
                {
                    "source": "NCI-GDC",
                    "source_api": self.client.base_url,
                    "transformation_version": request.transformation_version,
                    "snapshot_hash": digest,
                },
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        return snapshot


def map_snapshot_object(hit: dict[str, Any]) -> SnapshotObject:
    """Explicitly project a transport `/files` hit into the frozen object schema."""
    return SnapshotObject(
        file_id=hit.get("file_id"),
        file_name=hit.get("file_name"),
        file_size=hit.get("file_size"),
        md5sum=hit.get("md5sum"),
        access=hit.get("access"),
        data_type=hit.get("data_type"),
        data_format=hit.get("data_format"),
    )
