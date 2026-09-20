"""Canonical molecular schema v2: source observations, never inferred endpoints."""

from pydantic import Field, FiniteFloat, model_validator

from packages.schemas.identity import StrictRecord

MOLECULAR_SCHEMA_VERSION = "2"


class MolecularRecord(StrictRecord):
    case_id: str
    sample_id: str
    aliquot_id: str | None = None
    source_file_id: str
    source_submitter_id: str | None = None


class GeneRecord(MolecularRecord):
    gene_id: str
    source_gene_id: str
    gene_version: str | None = None
    normalization_version: str
    gene_symbol: str | None = None


class MutationRecord(GeneRecord):
    chromosome: str = Field(min_length=1)
    position: int = Field(ge=1, le=2**63 - 1)
    end_position: int = Field(ge=1, le=2**63 - 1)
    ref: str = Field(pattern=r"^(?:[ACGTN]+|-)$")
    alt: str = Field(pattern=r"^(?:[ACGTN]+|-)$")
    consequence: str | None = None
    variant_classification: str | None = None
    protein_change: str | None = None
    transcript_id: str | None = None
    ssm_id: str | None = None

    @model_validator(mode="after")
    def valid_variant(self):
        if self.position > self.end_position or self.ref == self.alt:
            raise ValueError("invalid_variant_coordinates_or_alleles")
        return self


class ExpressionRecord(GeneRecord):
    value: FiniteFloat = Field(ge=0)
    measurement_type: str = Field(min_length=1)


class CNVRecord(GeneRecord):
    cnv_value: FiniteFloat | None = Field(default=None, ge=0)
    min_copy_number: FiniteFloat | None = Field(default=None, ge=0)
    max_copy_number: FiniteFloat | None = Field(default=None, ge=0)
    cnv_class: str | None = None


class SegmentCNVRecord(MolecularRecord):
    chromosome: str = Field(min_length=1)
    start: int = Field(ge=1, le=2**63 - 1)
    end: int = Field(ge=1, le=2**63 - 1)
    probe_count: int | None = Field(default=None, ge=0, le=2**63 - 1)
    segment_mean: FiniteFloat

    @model_validator(mode="after")
    def valid_interval(self):
        if self.start > self.end:
            raise ValueError("reversed_segment_interval")
        return self


class ClinicalRecord(StrictRecord):
    case_id: str
    source_artifact_sha256: str
    diagnosis_id: str | None = None
    age_at_diagnosis: FiniteFloat | None = Field(default=None, ge=0)
    stage: str | None = None
    vital_status: str | None = None
    days_to_death: FiniteFloat | None = None
    days_to_last_follow_up: FiniteFloat | None = None
    gender: str | None = None
    race: str | None = None
    ethnicity: str | None = None
    diagnosis_json: str
    demographic_json: str
    follow_ups_json: str
    exposures_json: str
