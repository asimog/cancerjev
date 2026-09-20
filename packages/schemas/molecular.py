from typing import Literal

from pydantic import Field

from packages.schemas.identity import StrictRecord


class MutationRecord(StrictRecord):
    case_id: str
    sample_id: str
    aliquot_id: str | None = None
    gene_id: str
    gene_symbol: str
    chromosome: str
    position: int
    ref: str
    alt: str
    consequence: str | None = None
    protein_change: str | None = None
    ssm_id: str
    source_file_id: str


class ExpressionRecord(StrictRecord):
    case_id: str
    sample_id: str
    aliquot_id: str | None = None
    gene_id: str
    gene_symbol: str | None = None
    value: float
    measurement_type: str = Field(min_length=1)
    source_file_id: str


class CNVRecord(StrictRecord):
    case_id: str
    sample_id: str
    aliquot_id: str | None = None
    gene_id: str
    gene_symbol: str | None = None
    cnv_value: float
    cnv_class: str
    source_file_id: str


class SegmentCNVRecord(StrictRecord):
    case_id: str
    sample_id: str
    chromosome: str
    start: int
    end: int
    segment_mean: float
    source_file_id: str


class ClinicalRecord(StrictRecord):
    case_id: str
    age_at_diagnosis: float | None = None
    stage: str | None = None
    vital_status: str | None = None
    days_to_event: float | None = None
    event_type: Literal["death", "censored"] | None = None
