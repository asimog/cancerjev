from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LogicalSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(pattern=r"^[A-Z0-9]+-[A-Z0-9-]+$")
    gdc_release: str | None = None
    transformation_version: str = "logical-v1"
    schema_versions: dict[str, str] = Field(default_factory=lambda: {"identity": "1"})
    identity_mapping_version: str = "gdc-identity-v1"
    selection_policy_version: str = "open-project-files-v1"
    normalization_policy_version: str = "none"
    requested_fields: tuple[str, ...] = ()


class SnapshotObject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    file_id: str
    file_name: str
    file_size: int = Field(ge=0)
    md5sum: str
    access: str
    data_type: str | None = None
    data_format: str | None = None
    data_category: str | None = None
    experimental_strategy: str | None = None
    workflow_type: str | None = None


class SnapshotRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: str
    snapshot_hash: str
    project_id: str
    source: str = "NCI-GDC"
    source_api: str
    gdc_release: str | None
    query: dict[str, Any]
    transformation_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    objects: tuple[SnapshotObject, ...]
    case_ids: tuple[str, ...] = ()
    sample_ids: tuple[str, ...] = ()
    aliquot_ids: tuple[str, ...] = ()
    requested_fields: tuple[str, ...] = ()
    canonical_schema_versions: dict[str, str] = Field(default_factory=lambda: {"identity": "1"})
    normalization_metadata: dict[str, Any] = Field(default_factory=dict)
    upstream_provenance: dict[str, str] = Field(default_factory=dict)
    analytical_object_hashes: dict[str, str] = Field(default_factory=dict)
