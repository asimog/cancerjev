"""CancerJev-owned identity contracts; raw GDC JSON never crosses this boundary."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjectRecord(StrictRecord):
    project_id: str
    name: str | None = None
    primary_site: tuple[str, ...] = ()


class CaseRecord(StrictRecord):
    case_id: str
    submitter_id: str | None = None
    project_id: str


class SampleRecord(StrictRecord):
    sample_id: str
    case_id: str
    sample_submitter_id: str | None = None
    sample_type: str | None = None
    tumor_descriptor: str | None = None
    tissue_type: str | None = None


class AliquotRecord(StrictRecord):
    aliquot_id: str
    sample_id: str
    submitter_id: str | None = None


class FileRecord(StrictRecord):
    file_id: str
    file_name: str
    file_size: int = Field(ge=0)
    md5sum: str = Field(pattern=r"^[0-9a-fA-F]{32}$")
    access: Literal["open"]
    data_category: str | None = None
    data_type: str | None = None
    data_format: str | None = None
    experimental_strategy: str | None = None
    workflow_type: str | None = None


class FileSampleLink(StrictRecord):
    file_id: str
    case_id: str
    sample_id: str | None = None
    aliquot_id: str | None = None
