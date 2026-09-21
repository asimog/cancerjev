import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Page[T](BaseModel):
    items: list[T]
    limit: int
    offset: int


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    project_id: str
    name: str | None
    primary_site: list[str]
    created_at: datetime
    updated_at: datetime


class ArtifactRegistration(StrictModel):
    sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    size: int = Field(ge=0)
    media_type: str
    logical_role: str
    storage_backend: str
    storage_key: str
    source_gdc_uuid: str | None = None
    source_md5: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{32}$")
    parser_schema_version: str | None = None
    row_count: int | None = Field(default=None, ge=0)


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    object_id: str
    sha256: str
    size: int
    media_type: str
    logical_role: str
    source_gdc_uuid: str | None
    source_md5: str | None
    parser_schema_version: str | None
    row_count: int | None
    created_at: datetime


class SnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    snapshot_id: str
    snapshot_hash: str
    project_id: str
    status: str
    source_api: str
    gdc_release: str
    schema_versions: dict[str, str]
    policy_versions: dict[str, Any]
    manifest_sha256: str | None
    coverage_sha256: str | None
    identity_sha256: str | None
    provenance_sha256: str | None
    created_at: datetime
    published_at: datetime | None


class CohortCreate(StrictModel):
    snapshot_id: str
    definition_version: str = "1"
    definition: dict[str, Any]
    case_ids: list[str] = Field(default_factory=list)
    sample_ids: list[str] = Field(default_factory=list)
    exclusion_reasons: dict[str, str] = Field(default_factory=dict)
    selection_policy_version: str = "1"


class CohortResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cohort_id: str
    snapshot_id: str
    definition_version: str
    definition: dict[str, Any]
    content_hash: str
    case_ids: list[str]
    sample_ids: list[str]
    exclusion_reasons: dict[str, str]
    selection_policy_version: str
    created_at: datetime


class AnalysisInput(StrictModel):
    materialization_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    modality: Literal["mutation", "expression", "cnv", "segment_cnv", "clinical"]
    measurement_type: str


class ManifestRequest(StrictModel):
    file_ids: list[str] | None = Field(default=None, min_length=1, max_length=10000)


class AnalysisCreate(StrictModel):
    snapshot_id: str
    cohort_id: str
    engine: str
    engine_version: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    expected_input_artifacts: list[str] = Field(default_factory=list)
    input_materializations: list[AnalysisInput] = Field(min_length=1, max_length=10000)


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    analysis_id: uuid.UUID
    snapshot_id: str
    cohort_id: str | None
    engine: str
    engine_version: str
    parameters: dict[str, Any]
    expected_input_artifacts: list[str]
    input_materializations: list[AnalysisInput]
    state: str
    job_id: uuid.UUID | None
    error: str | None
    created_at: datetime
    queued_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    finding_id: str
    snapshot_id: str
    cohort_id: str | None
    analysis_id: uuid.UUID
    finding_type: str
    gene_id: str | None
    gene_symbol: str | None
    analysis_version: str
    result_hash: str | None
    payload: dict[str, Any]
    created_at: datetime


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_id: uuid.UUID
    event_type: str
    actor_id: str
    resource_type: str
    resource_id: str
    context: dict[str, Any]
    created_at: datetime
