"""CancerJev-owned identity contracts; raw GDC JSON never crosses this boundary."""

from collections.abc import Callable, Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def unique_records(
    records: Iterable[BaseModel], key: Callable[[BaseModel], str], *, label: str
) -> list[BaseModel]:
    """Collapse exact duplicates; reject conflicting records for one identity key.

    Last-write-wins dictionary behavior must never be a scientific policy:
    two records sharing a biological key with different canonical content
    fail deterministically instead of being silently collapsed.
    """
    by_key: dict[str, tuple[dict, BaseModel]] = {}
    for record in records:
        value = key(record)
        canonical = record.model_dump(mode="json")
        existing = by_key.get(value)
        if existing is None:
            by_key[value] = (canonical, record)
        elif existing[0] != canonical:
            raise ValueError(f"conflicting_{label}_identity")
    return [by_key[value][1] for value in sorted(by_key)]


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
