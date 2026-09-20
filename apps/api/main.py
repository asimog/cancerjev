from typing import Annotated

from fastapi import Depends, FastAPI, Query, status

from apps.api.config import Settings, settings
from packages.gdc.client import GDCClient
from packages.schemas.snapshot import LogicalSnapshotRequest, SnapshotRecord
from packages.storage.snapshots import FileSnapshotRepository
from workers.ingest.snapshot import LogicalSnapshotService

app = FastAPI(
    title="CancerJev API",
    version="0.1.0",
    description="Research use only. Not for diagnosis or treatment decisions.",
)


def get_settings() -> Settings:
    return settings


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/gdc/projects", tags=["gdc"])
async def projects(
    config: Annotated[Settings, Depends(get_settings)],
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    async with GDCClient.from_settings(config) as client:
        return await client.get_projects(size=size)


@app.post(
    "/v1/snapshots/logical",
    tags=["snapshots"],
    response_model=SnapshotRecord,
    status_code=status.HTTP_201_CREATED,
)
async def create_logical_snapshot(
    request: LogicalSnapshotRequest,
    config: Annotated[Settings, Depends(get_settings)],
) -> SnapshotRecord:
    repository = FileSnapshotRepository(config.snapshot_root)
    async with GDCClient.from_settings(config) as client:
        service = LogicalSnapshotService(client=client, repository=repository)
        return await service.create(request)
