from typing import Annotated, Never

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, status

from apps.api.config import Settings, settings
from packages.gdc.client import GDCClient
from packages.jev.client import JevClient
from packages.jev.schemas import (
    EvidenceJudgment,
    EvidenceJudgmentRequest,
    JevEvaluationRequest,
    JevEvaluationResponse,
)
from packages.schemas.snapshot import LogicalSnapshotRequest, SnapshotRecord
from packages.storage.snapshots import FileSnapshotRepository
from workers.ingest.snapshot import LogicalSnapshotService
from workers.validation.jev import JevEvidenceService

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


def _jev_client(config: Settings) -> JevClient:
    try:
        return JevClient.from_settings(config)
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def _raise_jev_gateway_error(error: httpx.HTTPError) -> Never:
    raise HTTPException(status_code=502, detail="Jev provider request failed") from error


@app.post("/v1/jev/evaluate", tags=["jev"], response_model=JevEvaluationResponse)
async def evaluate_with_jev(
    request: JevEvaluationRequest,
    config: Annotated[Settings, Depends(get_settings)],
) -> JevEvaluationResponse:
    """Evaluate TypeSafe Choice, Score, and Noul questions against shared state."""
    async with _jev_client(config) as client:
        try:
            return await client.evaluate(request)
        except httpx.HTTPError as error:
            _raise_jev_gateway_error(error)


@app.post(
    "/v1/jev/evidence-judgments",
    tags=["jev", "validation"],
    response_model=EvidenceJudgment,
)
async def judge_evidence(
    request: EvidenceJudgmentRequest,
    config: Annotated[Settings, Depends(get_settings)],
) -> EvidenceJudgment:
    """Run the canonical Jev evidence relationship classification."""
    async with _jev_client(config) as client:
        try:
            return await JevEvidenceService(client).judge(request)
        except httpx.HTTPError as error:
            _raise_jev_gateway_error(error)
