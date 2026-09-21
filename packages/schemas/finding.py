"""Computed scientific payload; authoritative identity is the publication envelope."""

from pydantic import Field

from packages.schemas.identity import StrictRecord


class Finding(StrictRecord):
    snapshot_id: str
    finding_type: str
    gene: str
    cohort_size: int = Field(ge=0)
    eligible_cases: int = Field(ge=0)
    eligible_case_ids: tuple[str, ...]
    eligible_sample_ids: tuple[str, ...] = ()
    n_effective: int = Field(ge=0)
    effect_size: float
    confidence_interval: tuple[float, float] | None = None
    p_value: float = Field(ge=0, le=1)
    q_value: float = Field(ge=0, le=1)
    missing_n: int = Field(ge=0)
    missing_fraction: float = Field(ge=0, le=1)
    qc_flags: tuple[str, ...] = ()
    confounder_flags: tuple[str, ...] = ()
    analysis_version: str
    evidence_ids: tuple[str, ...] = ()
    input_object_hashes: tuple[str, ...]
    result_hash: str
