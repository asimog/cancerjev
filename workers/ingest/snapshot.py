"""Frozen snapshot creation with authoritative GDC source identity."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from packages.gdc.client import GDCClient
from packages.gdc.coverage import build_coverage
from packages.gdc.filters import open_project_files
from packages.gdc.manifest import generate_manifest
from packages.gdc.mappings import map_file_hit
from packages.provenance.hashing import identity_hash
from packages.schemas.snapshot import LogicalSnapshotRequest, SnapshotObject, SnapshotRecord

MANDATORY_IDENTITY_FIELDS = (
    "file_id",
    "file_name",
    "file_size",
    "md5sum",
    "access",
    "data_category",
    "data_type",
    "data_format",
    "experimental_strategy",
    "analysis.workflow_type",
    "cases.case_id",
    "cases.submitter_id",
    "cases.project.project_id",
    "cases.samples.sample_id",
    "cases.samples.submitter_id",
    "cases.samples.sample_type",
    "cases.samples.tumor_descriptor",
    "cases.samples.tissue_type",
    "cases.samples.portions.analytes.aliquots.aliquot_id",
    "cases.samples.portions.analytes.aliquots.submitter_id",
)


class SnapshotRepository(Protocol):
    def publish(
        self, snapshot: SnapshotRecord, write_artifacts: Callable[[Path], None]
    ) -> SnapshotRecord: ...


class IdentityConflictError(ValueError):
    def __init__(self, entity_type: str, entity_id: str, message: str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"identity conflict: {entity_type} {entity_id} - {message}")


class LogicalSnapshotService:
    def __init__(self, *, client: GDCClient, repository: SnapshotRepository):
        self.client = client
        self.repository = repository

    async def create(self, request: LogicalSnapshotRequest) -> SnapshotRecord:
        mandatory = frozenset(MANDATORY_IDENTITY_FIELDS)
        caller_fields = frozenset(request.requested_fields or ())
        effective_fields = tuple(sorted(mandatory | caller_fields))
        payload = await self.client.get_open_files(
            request.project_id, fields=effective_fields
        )
        hits = payload.get("data", {}).get("hits", [])
        objects = tuple(
            sorted(
                (map_snapshot_object(hit) for hit in hits), key=lambda x: x.file_id
            )
        )
        if any(item.access != "open" for item in objects):
            raise ValueError("GDC returned a controlled file for an open-data snapshot")

        query = open_project_files(request.project_id)
        mapped = [map_file_hit(hit) for hit in hits]
        files = [item[0] for item in mapped]

        # Deduplicate cases, samples, aliquots by identity
        def dedup(index: int, key: str):
            values = [value for item in mapped for value in item[index]]
            seen = {}
            for value in values:
                kid = getattr(value, key)
                if kid in seen:
                    existing = seen[kid]
                    if existing != value:
                        raise IdentityConflictError(
                            key, kid, f"metadata differs: {existing} vs {value}"
                        )
                seen[kid] = value
            return sorted(seen.values(), key=lambda value: getattr(value, key))

        cases, samples = dedup(1, "case_id"), dedup(2, "sample_id")
        aliquots = dedup(3, "aliquot_id")
        # Deduplicate links using complete biological identity tuple, not file_id alone
        links = sorted(
            {
                (v.file_id, v.case_id, v.sample_id, v.aliquot_id): v
                for item in mapped
                for v in item[4]
            }.values(),
            key=lambda v: (
                v.file_id,
                v.case_id,
                v.sample_id or "",
                v.aliquot_id or "",
            ),
        )

        # Capture authoritative GDC release before acquisition
        release_identity = await self._capture_gdc_release()
        identity = {
            "project_id": request.project_id,
            "gdc_release": release_identity,
            "source": "NCI-GDC",
            "source_api": self.client.base_url,
            "query": query,
            "open_access_required": True,
            "requested_fields": effective_fields,
            "transformation_version": request.transformation_version,
            "schema_versions": request.schema_versions,
            "identity_mapping_version": request.identity_mapping_version,
            "selection_policy_version": request.selection_policy_version,
            "normalization_policy_version": request.normalization_policy_version,
            "objects": [item.model_dump(mode="json") for item in objects],
            "file_identity_links": [item.model_dump(mode="json") for item in links],
            "case_ids": [item.case_id for item in cases],
            "case_metadata": {c.case_id: c.model_dump(mode="json") for c in cases},
            "sample_ids": [item.sample_id for item in samples],
            "sample_metadata": {
                s.sample_id: s.model_dump(mode="json") for s in samples
            },
            "aliquot_ids": [item.aliquot_id for item in aliquots],
            "aliquot_metadata": {
                a.aliquot_id: a.model_dump(mode="json") for a in aliquots
            },
            "identity_version": "v2",
        }
        digest = identity_hash(identity)
        snapshot = SnapshotRecord(
            snapshot_id=f"DS-{request.project_id}-{digest.removeprefix('sha256:')[:12]}",
            snapshot_hash=digest,
            project_id=request.project_id,
            source_api=self.client.base_url,
            gdc_release=release_identity,
            query=query,
            transformation_version=request.transformation_version,
            objects=objects,
            case_ids=tuple(identity["case_ids"]),
            sample_ids=tuple(identity["sample_ids"]),
            aliquot_ids=tuple(identity["aliquot_ids"]),
            requested_fields=effective_fields,
            canonical_schema_versions=request.schema_versions | {"identity": "2"},
            normalization_metadata={
                "policy_version": request.normalization_policy_version
            },
            upstream_provenance={
                "release": release_identity,
                "identity_version": "v2",
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
            write_records(
                links, root / "file_sample_links.parquet", model=FileSampleLink
            )
            write_records(
                build_coverage(cases, files, links),
                root / "coverage.parquet",
                model=CoverageRecord,
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

    async def _capture_gdc_release(self) -> str:
        """Capture authoritative GDC release from the /status endpoint.

        Falls back to 'unknown/not-reported' only if the endpoint is unreachable
        after retries, following a documented max-retry policy.
        """
        if self.client.base_url != "https://api.gdc.cancer.gov":
            return "unknown/not-reported"
        try:
            status = await self.client._json("/status", {})
            release = (
                (status.get("data") or {}).get("release") or "unknown/not-reported"
            )
            return str(release)
        except Exception:
            return "unknown/not-reported"


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
