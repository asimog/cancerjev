from typing import Any, Protocol

from packages.gdc.filters import open_project_files
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
        objects = tuple(
            sorted(
                (SnapshotObject.model_validate(hit) for hit in hits),
                key=lambda item: item.file_id,
            )
        )
        if any(item.access != "open" for item in objects):
            raise ValueError("GDC returned a controlled file for an open-data snapshot")

        query = open_project_files(request.project_id)
        identity = {
            "project_id": request.project_id,
            "gdc_release": request.gdc_release,
            "query": query,
            "transformation_version": request.transformation_version,
            "objects": [item.model_dump(mode="json") for item in objects],
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
        )
        self.repository.save(snapshot)
        return snapshot
