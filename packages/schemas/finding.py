from typing import Annotated, Literal

from pydantic import Field, FiniteFloat

from packages.schemas.identity import StrictRecord


class LegacyFinding(StrictRecord):
    finding_id: str
    snapshot_id: str
    finding_type: str
    gene: str
    cohort_size: int = Field(ge=0)
    eligible_cases: int = Field(ge=0)
    eligible_case_ids: tuple[str, ...]
    eligible_sample_ids: tuple[str, ...] = ()
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


# V2 Findings preserve descriptive and non-estimable results without fake p-values.


class Eligibility(StrictRecord):
    unit: Literal["case", "sample"]
    total_n: int = Field(ge=0)
    eligible_n: int = Field(ge=0)
    eligible_ids: tuple[str, ...]
    eligible_case_ids: tuple[str, ...]
    eligible_sample_ids: tuple[str, ...]
    missing_ids: tuple[str, ...]
    missing_n: int = Field(ge=0)
    missing_fraction: FiniteFloat = Field(ge=0, le=1)
    excluded: dict[str, str]
    modality_eligible_ids: dict[str, tuple[str, ...]]
    duplicate_count: int = Field(ge=0)
    duplicate_policy: str = "duplicate-observations-v1"


class Correction(StrictRecord):
    method: Literal["benjamini-hochberg"] = "benjamini-hochberg"
    version: str = "bh-v1"
    family_id: str
    planned_hypotheses: int
    tested_hypotheses: int
    excluded_hypotheses: dict[str, str]


class FrequencyResult(StrictRecord):
    kind: Literal["frequency"] = "frequency"
    mutated_n: int
    frequency: FiniteFloat
    confidence_interval: tuple[FiniteFloat, FiniteFloat]
    mutated_ids: tuple[str, ...]
    metric: str = "masked_somatic_callset_recurrence"


class CountResult(StrictRecord):
    kind: Literal["count"] = "count"
    counts: dict[str, int]
    metric: str = "eligible_somatic_mutation_count"
    units: str = "distinct_source_variants"
    variant_policy: str = "observation-coordinate-alleles-v1"


class CNVFrequencyResult(StrictRecord):
    kind: Literal["cnv_frequency"] = "cnv_frequency"
    amplification_n: int
    deletion_n: int
    amplification_frequency: FiniteFloat
    deletion_frequency: FiniteFloat
    amplification_ids: tuple[str, ...]
    deletion_ids: tuple[str, ...]
    amplification_threshold: FiniteFloat
    deletion_threshold: FiniteFloat
    threshold_version: str = "absolute-copy-number-cutoffs-v1"


class OutlierResult(StrictRecord):
    kind: Literal["outlier"] = "outlier"
    center: FiniteFloat
    mad: FiniteFloat
    variance: FiniteFloat
    threshold: FiniteFloat
    threshold_version: str = "modified-mad-v1"
    outlier_ids: tuple[str, ...]
    status: Literal["estimable", "constant", "zero_mad"]


class AssociationResult(StrictRecord):
    kind: Literal["association"] = "association"
    test: Literal["welch_t", "pearson"]
    effect: FiniteFloat
    confidence_interval: tuple[FiniteFloat, FiniteFloat]
    p: FiniteFloat = Field(ge=0, le=1)
    q: FiniteFloat | None = Field(default=None, ge=0, le=1)
    group_ids: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    group_n: dict[str, int] = Field(default_factory=dict)


class ContingencyResult(StrictRecord):
    kind: Literal["contingency"] = "contingency"
    table: tuple[tuple[int, int], tuple[int, int]]
    odds_ratio: FiniteFloat | None
    odds_ratio_status: Literal["finite", "infinite", "undefined"]
    direction: Literal["cooccurrence", "mutual_exclusivity", "neutral"]
    p: FiniteFloat = Field(ge=0, le=1)
    q: FiniteFloat | None = Field(default=None, ge=0, le=1)
    test: str = "fisher_exact_two_sided"


class SurvivalCurve(StrictRecord):
    n: int
    events: int
    censored: int
    median_survival: FiniteFloat | None
    median_status: Literal["estimated", "not_reached"]
    timeline: tuple[FiniteFloat, ...]
    survival: tuple[FiniteFloat, ...]
    lower: tuple[FiniteFloat, ...]
    upper: tuple[FiniteFloat, ...]


class SurvivalResult(StrictRecord):
    kind: Literal["survival"] = "survival"
    endpoint_version: str = "gdc-overall-survival-v1"
    curves: dict[str, SurvivalCurve]
    group_ids: dict[str, tuple[str, ...]]
    test: str = "logrank"
    test_status: str
    p: FiniteFloat | None = Field(default=None, ge=0, le=1)
    q: FiniteFloat | None = Field(default=None, ge=0, le=1)


class QCResult(StrictRecord):
    kind: Literal["qc"] = "qc"
    policy_version: str = "group-imbalance-indicators-v1"
    group_n: dict[str, int]
    age_mean: dict[str, FiniteFloat | None]
    stage_distribution: dict[str, dict[str, int]]
    missing_fraction: dict[str, dict[str, FiniteFloat]]
    modality_coverage: dict[str, dict[str, FiniteFloat | None]]
    selected_samples_per_case: dict[str, FiniteFloat]
    flags: tuple[str, ...]


class NonEstimableResult(StrictRecord):
    kind: Literal["non_estimable"] = "non_estimable"
    reason: str


ScientificResult = Annotated[
    FrequencyResult | CountResult | CNVFrequencyResult | OutlierResult | AssociationResult
    | ContingencyResult | SurvivalResult | QCResult | NonEstimableResult,
    Field(discriminator="kind"),
]


class Finding(StrictRecord):
    schema_version: Literal["2"] = "2"
    finding_id: str
    result_hash: str
    snapshot_id: str
    cohort_id: str
    analysis_id: str
    engine: str
    engine_version: str
    finding_type: str
    context: tuple[str, ...]
    eligibility: Eligibility
    result: ScientificResult
    parameters: dict
    input_manifest: dict
    correction: Correction | None = None
    qc_flags: tuple[str, ...] = ()
    confounder_flags: tuple[str, ...] = ()
