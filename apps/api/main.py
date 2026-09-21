import json
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pyarrow import parquet as pq
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.config import Settings, settings
from packages.database.session import session_factory
from packages.gdc.client import GDCClient
from packages.gdc.slicing import GDCBAMSlicingClient
from packages.partition import DatasetPartitioner
from packages.provenance.hashing import sha256_file
from packages.resources.materialization import MaterializationService
from packages.resources.service import (
    DurableResourceService,
    ResourceConflictError,
    ResourceNotFoundError,
)
from packages.schemas.materialization import MaterializationRequest
from packages.schemas.resources import (
    AnalysisCreate,
    AnalysisResponse,
    ArtifactRegistration,
    ArtifactResponse,
    CohortCreate,
    CohortResponse,
    FindingResponse,
    Page,
    ProjectResponse,
    SnapshotResponse,
)
from packages.schemas.snapshot import LogicalSnapshotRequest, SnapshotRecord
from packages.storage.config import StorageSettings
from packages.storage.snapshots import FileSnapshotRepository
from workers.ingest.snapshot import LogicalSnapshotService


@asynccontextmanager
async def lifespan(app: FastAPI):
    factory = session_factory(settings.database_url)
    with factory() as session:
        session.execute(text("SELECT 1"))
    app.state.session_factory = factory
    yield


app = FastAPI(
    title="CancerJev API",
    version="0.2.0",
    description="Research use only. Not for diagnosis or treatment decisions.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["content-type", "idempotency-key"],
)


def get_settings() -> Settings:
    return settings


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


Db = Annotated[Session, Depends(get_session)]
Config = Annotated[Settings, Depends(get_settings)]


@app.exception_handler(ResourceNotFoundError)
async def not_found_handler(_request: Request, exc: ResourceNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404, content={"error": {"code": "not_found", "message": str(exc)}}
    )


@app.exception_handler(ResourceConflictError)
async def conflict_handler(_request: Request, exc: ResourceConflictError) -> JSONResponse:
    return JSONResponse(
        status_code=409, content={"error": {"code": "conflict", "message": str(exc)}}
    )


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/gdc/projects", tags=["gdc"])
async def gdc_projects(
    config: Config,
    db: Db,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    async with GDCClient.from_settings(config) as client:
        payload = await client.get_projects(size=size)
    with db.begin():
        service = DurableResourceService(db)
        for hit in payload["data"]["hits"]:
            service.save_project(
                hit["project_id"], name=hit.get("name"), primary_site=hit.get("primary_site") or []
            )
    return payload


@app.get("/v1/projects", response_model=Page[ProjectResponse], tags=["resources"])
def projects(
    db: Db,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ProjectResponse]:
    values = DurableResourceService(db).projects.list(limit=limit, offset=offset)
    return Page(items=values, limit=limit, offset=offset)


@app.get("/v1/projects/{project_id}", response_model=ProjectResponse, tags=["resources"])
def project(project_id: str, db: Db):
    value = DurableResourceService(db).projects.get(project_id)
    if value is None:
        raise ResourceNotFoundError("project not found")
    return value


@app.post(
    "/v1/snapshots/logical",
    tags=["snapshots"],
    response_model=SnapshotRecord,
    status_code=status.HTTP_201_CREATED,
)
async def create_logical_snapshot(request: LogicalSnapshotRequest, config: Config, db: Db):
    repository = FileSnapshotRepository(config.snapshot_root)
    async with GDCClient.from_settings(config) as client:
        snapshot = await LogicalSnapshotService(client=client, repository=repository).create(
            request
        )
    registrations = _snapshot_artifacts(config.snapshot_root, snapshot, config)
    with db.begin():
        DurableResourceService(db).register_snapshot(snapshot, registrations)
    return snapshot


@app.get("/v1/snapshots", response_model=Page[SnapshotResponse], tags=["resources"])
def snapshots(
    db: Db,
    project_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    values = DurableResourceService(db).snapshots.list(
        project_id=project_id, limit=limit, offset=offset
    )
    return Page(items=values, limit=limit, offset=offset)


@app.get("/v1/snapshots/{snapshot_id}", response_model=SnapshotResponse, tags=["resources"])
def snapshot(snapshot_id: str, db: Db):
    value = DurableResourceService(db).snapshots.get(snapshot_id)
    if value is None:
        raise ResourceNotFoundError("snapshot not found")
    return value


@app.get(
    "/v1/snapshots/{snapshot_id}/artifacts",
    response_model=Page[ArtifactResponse],
    tags=["resources"],
)
def snapshot_artifacts(snapshot_id: str, db: Db):
    service = DurableResourceService(db)
    value = service.snapshots.get(snapshot_id)
    if value is None:
        raise ResourceNotFoundError("snapshot not found")
    artifacts = service.artifacts.list_for_snapshot(snapshot_id)
    return Page(items=artifacts, limit=100, offset=0)


@app.get("/v1/artifacts/{sha256}", response_model=ArtifactResponse, tags=["resources"])
def artifact(sha256: str, db: Db):
    value = DurableResourceService(db).artifacts.get(sha256)
    if value is None:
        raise ResourceNotFoundError("artifact not found")
    return value


@app.post("/v1/cohorts", response_model=CohortResponse, status_code=201, tags=["resources"])
def create_cohort(request: CohortCreate, db: Db):
    with db.begin():
        return DurableResourceService(db).create_cohort(request)


@app.get("/v1/cohorts", response_model=Page[CohortResponse], tags=["resources"])
def cohorts(
    db: Db,
    snapshot_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    values = DurableResourceService(db).cohorts.list(
        snapshot_id=snapshot_id, limit=limit, offset=offset
    )
    return Page(items=values, limit=limit, offset=offset)


@app.get("/v1/cohorts/{cohort_id}", response_model=CohortResponse, tags=["resources"])
def cohort(cohort_id: str, db: Db):
    value = DurableResourceService(db).cohorts.get(cohort_id)
    if value is None:
        raise ResourceNotFoundError("cohort not found")
    return value


@app.post("/v1/analyses", response_model=AnalysisResponse, status_code=201, tags=["resources"])
def create_analysis(
    request: AnalysisCreate,
    db: Db,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
):
    with db.begin():
        return DurableResourceService(db).create_analysis(request, idempotency_key)


@app.get("/v1/analyses", response_model=Page[AnalysisResponse], tags=["resources"])
def analyses(
    db: Db,
    snapshot_id: str | None = None,
    state: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    values = DurableResourceService(db).analyses.list(
        snapshot_id=snapshot_id, state=state, limit=limit, offset=offset
    )
    return Page(items=values, limit=limit, offset=offset)


@app.get("/v1/analyses/{analysis_id}", response_model=AnalysisResponse, tags=["resources"])
def analysis(analysis_id: str, db: Db):
    value = DurableResourceService(db).analyses.get(analysis_id)
    if value is None:
        raise ResourceNotFoundError("analysis not found")
    return value


@app.get("/v1/findings", response_model=Page[FindingResponse], tags=["resources"])
def findings(
    db: Db,
    snapshot_id: str | None = None,
    cohort_id: str | None = None,
    analysis_id: str | None = None,
    finding_type: str | None = None,
    gene: str | None = None,
    result_hash: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    values = DurableResourceService(db).findings.list(
        snapshot_id=snapshot_id,
        cohort_id=cohort_id,
        analysis_id=analysis_id,
        finding_type=finding_type,
        gene=gene,
        result_hash=result_hash,
        limit=limit,
        offset=offset,
    )
    return Page(items=values, limit=limit, offset=offset)


@app.get("/v1/findings/{finding_id}", response_model=FindingResponse, tags=["resources"])
def finding(finding_id: str, db: Db):
    value = DurableResourceService(db).findings.get(finding_id)
    if value is None:
        raise ResourceNotFoundError("finding not found")
    return value


@app.post("/v1/materializations", status_code=201, tags=["gdc"])
async def request_materialization(
    request: MaterializationRequest,
    config: Config,
    db: Db,
):
    """Enqueue a materialization job for an already-registered source."""
    settings_storage = config.storage_settings
    store = settings_storage.store()
    service = MaterializationService(DurableResourceService(db), store, settings_storage)
    with db.begin():
        result = service.run(request)
    return result


@app.post("/v1/partitions", status_code=201, tags=["resources"])
def create_partition(
    snapshot_id: str,
    case_ids: list[str],
    sample_ids: list[str],
    aliquot_ids: list[str],
    db: Db,
):
    """Create and persist discovery/validation partition assignment for a snapshot."""
    partitioner = DatasetPartitioner()
    discovery, validation = partitioner.assign(
        snapshot_id,
        tuple(case_ids),
        tuple(sample_ids),
        tuple(aliquot_ids),
    )
    from packages.database.models import PartitionSet
    existing = db.query(PartitionSet).filter(
        PartitionSet.snapshot_id == snapshot_id,
        PartitionSet.assignment_hash == discovery.assignment_hash
    ).first()
    if existing is None:
        partition_set = PartitionSet(
            partition_set_id=f"PS-{uuid.uuid4().hex[:12]}",
            snapshot_id=snapshot_id,
            seed=discovery.seed,
            split_fraction=discovery.split_fraction,
            assignment_hash=discovery.assignment_hash,
            discovery_case_ids=list(discovery.case_ids),
            validation_case_ids=list(validation.case_ids),
            discovery_sample_ids=list(discovery.sample_ids),
            validation_sample_ids=list(validation.sample_ids),
            discovery_aliquot_ids=list(discovery.aliquot_ids),
            validation_aliquot_ids=list(validation.aliquot_ids),
        )
        db.add(partition_set)
        db.flush()
    return {
        "partition_set_id": partition_set.partition_set_id,
        "discovery": {
            "partition_id": discovery.partition_id,
            "partition": "DISCOVERY",
            "case_ids": discovery.case_ids,
            "sample_ids": discovery.sample_ids,
            "aliquot_ids": discovery.aliquot_ids,
            "assignment_hash": discovery.assignment_hash,
        },
        "validation": {
            "partition_id": validation.partition_id,
            "partition": "VALIDATION",
            "case_ids": validation.case_ids,
            "sample_ids": validation.sample_ids,
            "aliquot_ids": validation.aliquot_ids,
            "assignment_hash": validation.assignment_hash,
        },
    }


@app.get("/v1/bam/slice", tags=["gdc"])
async def slice_bam(
    file_uuid: str,
    gene: str | None = None,
    region: str | None = None,
):
    """Slice an open-access BAM by gene or genomic region. No auth required."""
    client = GDCBAMSlicingClient()
    try:
        if gene:
            data = await client.slice_by_gene(file_uuid, [gene])
        elif region:
            data = await client.slice_by_region(file_uuid, [region])
        else:
            data = await client.header_only(file_uuid)
    finally:
        await client.aclose()
    return Response(content=data, media_type="application/octet-stream")


def _snapshot_artifacts(
    root: Path, snapshot: SnapshotRecord, config: Settings | None = None
) -> list[ArtifactRegistration]:
    directory = root / snapshot.project_id / snapshot.snapshot_id
    marker = json.loads((directory / "COMPLETE.json").read_text(encoding="utf-8"))
    storage_settings = (
        config.storage_settings if config else StorageSettings()
    )
    storage_backend = storage_settings.object_backend
    roles = {
        "manifest.tsv": "manifest",
        "coverage.parquet": "coverage",
        "file_sample_links.parquet": "identity_links",
        "provenance.json": "provenance",
    }
    registrations = []
    for name, digest in marker["artifact_hashes"].items():
        path = directory / name
        if sha256_file(str(path)) != digest:
            raise HTTPException(409, "published snapshot artifact hash mismatch")
        registrations.append(
            ArtifactRegistration(
                sha256=digest,
                size=path.stat().st_size,
                media_type=_media_type(name),
                logical_role=roles.get(name, name.removesuffix(".parquet").removesuffix(".json")),
                storage_backend=storage_backend,
                storage_key=f"{snapshot.project_id}/{snapshot.snapshot_id}/{name}",
                parser_schema_version="identity-v1" if name.endswith(".parquet") else None,
                row_count=pq.ParquetFile(path).metadata.num_rows
                if name.endswith(".parquet")
                else None,
            )
        )
    return registrations


def _media_type(name: str) -> str:
    if name.endswith(".parquet"):
        return "application/vnd.apache.parquet"
    if name.endswith(".json"):
        return "application/json"
    return "text/tab-separated-values"
