import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from packages.gdc.client import OPEN_FILE_FIELDS
from packages.gdc.coverage import build_coverage
from packages.gdc.filters import open_project_files
from packages.gdc.manifest import generate_manifest
from packages.gdc.mappings import map_file_hit
from packages.gdc.policy import SOURCE_POLICY_VERSION, official_api, require_open
from packages.provenance.hashing import canonical_hash
from packages.schemas.identity import unique_records
from packages.schemas.snapshot import LogicalSnapshotRequest, SnapshotObject, SnapshotRecord

#: v2 hashes complete normalized case/sample/aliquot records; v1 hashed ID lists.
SNAPSHOT_IDENTITY_VERSION = 2


class SnapshotRepository(Protocol):
    def publish(
        self, snapshot: SnapshotRecord, write_artifacts: Callable[[Path], None]
    ) -> SnapshotRecord: ...


class LogicalSnapshotService:
    def __init__(self, *, client: Any, repository: SnapshotRepository):
        self.client = client
        self.repository = repository

    async def create(self, request: LogicalSnapshotRequest) -> SnapshotRecord:
        official_api(self.client.base_url)
        status_before = await self.client.status()
        requested_fields = tuple(sorted(set(request.requested_fields) | set(OPEN_FILE_FIELDS)))
        payload = await self.client.get_open_files(request.project_id, fields=requested_fields)
        status_after = await self.client.status()
        if status_before != status_after:
            raise ValueError("GDC status changed during snapshot discovery; retry acquisition")
        hits = payload.get("data", {}).get("hits", [])
        # Raw GDC hits deliberately never cross the canonical boundary.  GDC adds
        # requested/nested fields over time, while SnapshotObject remains strict.
        objects = tuple(sorted((map_snapshot_object(hit) for hit in hits), key=lambda x: x.file_id))
        for item in objects:
            require_open(item.access)

        query = open_project_files(request.project_id)
        mapped = [map_file_hit(hit) for hit in hits]
        files = [item[0] for item in mapped]

        # Conflicting duplicate biological records must fail deterministically;
        # exact duplicates collapse. Records are order-canonical by identity key.
        cases = unique_records(
            (record for item in mapped for record in item[1]), lambda r: r.case_id, label="case"
        )
        samples = unique_records(
            (record for item in mapped for record in item[2]),
            lambda r: r.sample_id,
            label="sample",
        )
        aliquots = unique_records(
            (record for item in mapped for record in item[3]),
            lambda r: r.aliquot_id,
            label="aliquot",
        )
        links = unique_records(
            (record for item in mapped for record in item[4]),
            lambda r: (r.file_id, r.case_id, r.sample_id or "", r.aliquot_id or ""),
            label="file_identity_link",
        )
        release_identity = status_before["data_release"]
        identity = {
            "identity_version": SNAPSHOT_IDENTITY_VERSION,
            "project_id": request.project_id,
            "gdc_release": release_identity,
            "source_policy_version": SOURCE_POLICY_VERSION,
            "gdc_status": status_before,
            "source": "NCI-GDC",
            "source_api": self.client.base_url,
            "query": query,
            "open_access_required": True,
            "requested_fields": requested_fields,
            "transformation_version": request.transformation_version,
            "schema_versions": request.schema_versions,
            "identity_mapping_version": request.identity_mapping_version,
            "selection_policy_version": request.selection_policy_version,
            "normalization_policy_version": request.normalization_policy_version,
            "objects": [item.model_dump(mode="json") for item in objects],
            "file_identity_links": [item.model_dump(mode="json") for item in links],
            "cases": [item.model_dump(mode="json") for item in cases],
            "samples": [item.model_dump(mode="json") for item in samples],
            "aliquots": [item.model_dump(mode="json") for item in aliquots],
        }
        digest = canonical_hash(identity)
        snapshot = SnapshotRecord(
            snapshot_id=f"DS-{request.project_id}-{digest.removeprefix('sha256:')[:12]}",
            snapshot_hash=digest,
            project_id=request.project_id,
            source_api=self.client.base_url,
            gdc_release=release_identity,
            query=query,
            transformation_version=request.transformation_version,
            identity_version=SNAPSHOT_IDENTITY_VERSION,
            objects=objects,
            case_ids=tuple(record.case_id for record in cases),
            sample_ids=tuple(record.sample_id for record in samples),
            aliquot_ids=tuple(record.aliquot_id for record in aliquots),
            requested_fields=requested_fields,
            canonical_schema_versions=request.schema_versions,
            normalization_metadata={"policy_version": request.normalization_policy_version},
            upstream_provenance={
                "release": release_identity,
                "source_policy_version": SOURCE_POLICY_VERSION,
                "status_endpoint": self.client.base_url + "/status",
                "status": status_before,
            },
        )

        def write_artifacts(root: Path) -> None:
            from packages.gdc.coverage import CoverageRecord
            from packages.schemas.identity import (
                AliquotRecord,
                CaseRecord,
                FileRecord,
                FileSampleLink,
                SampleRecord,
            )
            from packages.storage.parquet import write_records

            (root / "manifest.tsv").write_bytes(generate_manifest(files))
            write_records(cases, root / "cases.parquet", model=CaseRecord)
            write_records(samples, root / "samples.parquet", model=SampleRecord)
            write_records(aliquots, root / "aliquots.parquet", model=AliquotRecord)
            write_records(files, root / "files.parquet", model=FileRecord)
            write_records(links, root / "file_sample_links.parquet", model=FileSampleLink)
            write_records(
                build_coverage(cases, files, links), root / "coverage.parquet", model=CoverageRecord
            )
            (root / "provenance.json").write_text(
                json.dumps(
                    {"canonical_identity": identity, "snapshot_hash": digest},
                    sort_keys=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

        return self.repository.publish(snapshot, write_artifacts)


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
        data_category=hit.get("data_category"),
        experimental_strategy=hit.get("experimental_strategy"),
        workflow_type=(hit.get("analysis") or {}).get("workflow_type"),
    )
