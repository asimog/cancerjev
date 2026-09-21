import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"
    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None]
    primary_site: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DatasetSnapshot(Base):
    __tablename__ = "dataset_snapshots"
    snapshot_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    snapshot_hash: Mapped[str] = mapped_column(String(71), unique=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"))
    provenance: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default="published")
    source_api: Mapped[str] = mapped_column(String(500))
    gdc_release: Mapped[str] = mapped_column(String(100))
    schema_versions: Mapped[dict] = mapped_column(JSONB, default=dict)
    policy_versions: Mapped[dict] = mapped_column(JSONB, default=dict)
    manifest_sha256: Mapped[str | None] = mapped_column(ForeignKey("dataset_objects.sha256"))
    coverage_sha256: Mapped[str | None] = mapped_column(ForeignKey("dataset_objects.sha256"))
    identity_sha256: Mapped[str | None] = mapped_column(ForeignKey("dataset_objects.sha256"))
    provenance_sha256: Mapped[str | None] = mapped_column(ForeignKey("dataset_objects.sha256"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("status IN ('staging','published','failed')", name="ck_snapshots_status"),
        Index("ix_snapshots_project_created", "project_id", "created_at"),
    )


class DatasetObject(Base):
    __tablename__ = "dataset_objects"
    sha256: Mapped[str] = mapped_column(String(71), primary_key=True)
    size: Mapped[int] = mapped_column(BigInteger)
    media_type: Mapped[str] = mapped_column(String(100))
    logical_role: Mapped[str] = mapped_column(String(100))
    storage_backend: Mapped[str] = mapped_column(String(30))
    storage_key: Mapped[str] = mapped_column(String(1000), unique=True)
    source_gdc_uuid: Mapped[str | None] = mapped_column(String(100))
    source_md5: Mapped[str | None] = mapped_column(String(32))
    parser_schema_version: Mapped[str | None] = mapped_column(String(100))
    row_count: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def object_id(self) -> str:
        return self.sha256


class SnapshotArtifact(Base):
    __tablename__ = "snapshot_artifacts"
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_snapshots.snapshot_id"), primary_key=True
    )
    logical_role: Mapped[str] = mapped_column(String(100), primary_key=True)
    sha256: Mapped[str] = mapped_column(ForeignKey("dataset_objects.sha256"), index=True)


class MaterializationSource(Base):
    __tablename__ = "materialization_sources"
    source_id: Mapped[str] = mapped_column(String(71), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("dataset_snapshots.snapshot_id"))
    sha256: Mapped[str] = mapped_column(ForeignKey("dataset_objects.sha256"))
    source_file_id: Mapped[str | None] = mapped_column(String(100))
    source_metadata: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Materialization(Base):
    __tablename__ = "materializations"
    materialization_id: Mapped[str] = mapped_column(String(71), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("dataset_snapshots.snapshot_id"))
    source_id: Mapped[str] = mapped_column(ForeignKey("materialization_sources.source_id"))
    output_sha256: Mapped[str] = mapped_column(ForeignKey("dataset_objects.sha256"))
    diagnostics_sha256: Mapped[str] = mapped_column(ForeignKey("dataset_objects.sha256"))
    modality: Mapped[str] = mapped_column(String(40))
    measurement_type: Mapped[str] = mapped_column(String(50))
    parser_name: Mapped[str] = mapped_column(String(100))
    parser_version: Mapped[str] = mapped_column(String(40))
    schema_version: Mapped[str] = mapped_column(String(40))
    normalization_version: Mapped[str] = mapped_column(String(100))
    selection_version: Mapped[str] = mapped_column(String(100))
    logical_sha256: Mapped[str] = mapped_column(String(71))
    row_count: Mapped[int] = mapped_column(BigInteger)
    diagnostics_summary: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index("ix_materializations_lookup", "snapshot_id", "modality", "measurement_type"),
        CheckConstraint("row_count >= 0", name="ck_materialization_rows"),
    )


class Case(Base):
    __tablename__ = "cases"
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"))
    submitter_id: Mapped[str | None] = mapped_column(String(100))


class Sample(Base):
    __tablename__ = "samples"
    sample_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.case_id"))
    sample_type: Mapped[str | None] = mapped_column(String(100))


class Aliquot(Base):
    __tablename__ = "aliquots"
    aliquot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    sample_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("samples.sample_id"))


class SnapshotFile(Base):
    __tablename__ = "snapshot_files"
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_snapshots.snapshot_id"), primary_key=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    md5sum: Mapped[str] = mapped_column(String(32))
    sha256: Mapped[str | None] = mapped_column(String(71))


class Analysis(Base):
    __tablename__ = "analyses"
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("dataset_snapshots.snapshot_id"))
    cohort_id: Mapped[str | None] = mapped_column(ForeignKey("cohorts.cohort_id"))
    engine: Mapped[str] = mapped_column(String(100))
    engine_version: Mapped[str] = mapped_column(String(100))
    purpose: Mapped[str] = mapped_column(String(30), default="EXPLORATORY")
    state: Mapped[str] = mapped_column(String(30))
    parameters: Mapped[dict] = mapped_column(JSONB)
    input_materializations: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    execution_manifest_hash: Mapped[str | None] = mapped_column(String(71))
    expected_input_artifacts: Mapped[list[str]] = mapped_column(JSONB, default=list)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.job_id"), unique=True)
    partition_set_id: Mapped[str | None] = mapped_column(String(100))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "state IN ('requested','queued','running','completed','failed','cancelled')",
            name="ck_analyses_state",
        ),
        Index("ix_analyses_snapshot_created", "snapshot_id", "created_at"),
        Index("ix_analyses_cohort_created", "cohort_id", "created_at"),
    )


class Finding(Base):
    __tablename__ = "findings"
    finding_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.analysis_id"))
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("dataset_snapshots.snapshot_id"))
    cohort_id: Mapped[str | None] = mapped_column(ForeignKey("cohorts.cohort_id"))
    finding_type: Mapped[str] = mapped_column(String(100))
    gene_id: Mapped[str | None] = mapped_column(String(100))
    gene_symbol: Mapped[str | None] = mapped_column(String(100))
    analysis_version: Mapped[str] = mapped_column(String(100))
    result_hash: Mapped[str | None] = mapped_column(String(71))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index("ix_findings_snapshot", "snapshot_id"),
        Index("ix_findings_cohort", "cohort_id"),
        Index("ix_findings_analysis", "analysis_id"),
        Index("ix_findings_type", "finding_type"),
        Index("ix_findings_gene", "gene_symbol"),
        Index("ix_findings_result_hash", "result_hash"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(String(200), default="system")
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str] = mapped_column(String(200))
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Cohort(Base):
    __tablename__ = "cohorts"
    cohort_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("dataset_snapshots.snapshot_id"))
    definition: Mapped[dict] = mapped_column(JSONB)
    definition_version: Mapped[str] = mapped_column(String(100))
    case_ids: Mapped[list] = mapped_column(JSONB)
    sample_ids: Mapped[list] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(71), unique=True)
    exclusion_reasons: Mapped[dict] = mapped_column(JSONB, default=dict)
    selection_policy_version: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_type: Mapped[str] = mapped_column(String(80), index=True)
    state: Mapped[str] = mapped_column(String(20), index=True, default="queued")
    payload: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict | None] = mapped_column(JSONB)
    lease_owner: Mapped[str | None] = mapped_column(String(200))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued','claimed','running','succeeded','failed','cancelled')",
            name="ck_jobs_state",
        ),
        Index("ix_jobs_claim", "state", "job_type", "created_at"),
    )


class JobAttempt(Base):
    __tablename__ = "job_attempts"
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.job_id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    worker_id: Mapped[str] = mapped_column(String(200))
    attempt_token: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    scope: Mapped[str] = mapped_column(String(100), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(71))
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SearchRun(Base):
    __tablename__ = "search_runs"
    search_run_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("dataset_snapshots.snapshot_id"))
    cohort_id: Mapped[str] = mapped_column(ForeignKey("cohorts.cohort_id"))
    purpose: Mapped[str] = mapped_column(String(30), default="EXPLORATORY")
    gdc_api_version: Mapped[str | None] = mapped_column(String(100))
    gdc_release: Mapped[str | None] = mapped_column(String(100))
    search_policy_version: Mapped[str] = mapped_column(String(40))
    search_families: Mapped[list[str]] = mapped_column(JSONB, default=list)
    engines_used: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    state: Mapped[str] = mapped_column(String(30), default="running")
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index("ix_search_snapshot", "snapshot_id"),
        Index("ix_search_cohort", "cohort_id"),
    )


class MultipleTestingFamily(Base):
    __tablename__ = "multiple_testing_families"
    family_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    search_run_id: Mapped[str] = mapped_column(ForeignKey("search_runs.search_run_id"))
    family_name: Mapped[str] = mapped_column(String(100))
    correction_method: Mapped[str] = mapped_column(String(30))
    n_planned: Mapped[int] = mapped_column(Integer, default=0)
    n_tested: Mapped[int] = mapped_column(Integer, default=0)
    n_excluded: Mapped[int] = mapped_column(Integer, default=0)
    n_significant_at_005: Mapped[int | None] = mapped_column(Integer)
    n_significant_at_01: Mapped[int | None] = mapped_column(Integer)
    correction_version: Mapped[str] = mapped_column(String(40), default="bh-v1")
    family_hash: Mapped[str] = mapped_column(String(71))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidateObservation(Base):
    __tablename__ = "candidate_observations"
    candidate_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    search_run_id: Mapped[str] = mapped_column(ForeignKey("search_runs.search_run_id"))
    family: Mapped[str] = mapped_column(String(40))
    observation_type: Mapped[str] = mapped_column(String(40))
    gene_id: Mapped[str | None] = mapped_column(String(100))
    gene_symbol: Mapped[str | None] = mapped_column(String(100))
    engine: Mapped[str] = mapped_column(String(100))
    engine_version: Mapped[str] = mapped_column(String(40))
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    purpose: Mapped[str] = mapped_column(String(30), default="EXPLORATORY")
    snapshot_hash: Mapped[str] = mapped_column(String(71))
    cohort_hash: Mapped[str] = mapped_column(String(71))
    materialization_hashes: Mapped[dict] = mapped_column(JSONB, default=dict)
    eligibility_hash: Mapped[str] = mapped_column(String(71))
    n: Mapped[int] = mapped_column(Integer, default=0)
    effect: Mapped[float | None] = mapped_column(nullable=True)
    ci_lower: Mapped[float | None] = mapped_column(nullable=True)
    ci_upper: Mapped[float | None] = mapped_column(nullable=True)
    p_value: Mapped[float | None] = mapped_column(nullable=True)
    q_value: Mapped[float | None] = mapped_column(nullable=True)
    missingness: Mapped[float] = mapped_column(nullable=True, default=0.0)
    multiple_testing_family_id: Mapped[str | None] = mapped_column(
        ForeignKey("multiple_testing_families.family_id")
    )
    multiple_testing_correction: Mapped[str | None] = mapped_column(String(30))
    result_kind: Mapped[str] = mapped_column(String(30), default="estimable")
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    eligible_n: Mapped[int] = mapped_column(Integer, default=0)
    max_n: Mapped[int] = mapped_column(Integer, default=0)
    flags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    excluded: Mapped[dict] = mapped_column(JSONB, default=dict)
    identity_hash: Mapped[str] = mapped_column(String(71))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        Index("ix_candidate_search", "search_run_id"),
        Index("ix_candidate_family", "multiple_testing_family_id"),
        Index("ix_candidate_gene", "gene_id"),
    )


class PartitionSet(Base):
    __tablename__ = "partition_sets"
    partition_set_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("dataset_snapshots.snapshot_id"))
    seed: Mapped[str] = mapped_column(String(100))
    split_fraction: Mapped[float]
    assignment_hash: Mapped[str] = mapped_column(String(71))
    discovery_case_ids: Mapped[list] = mapped_column(JSONB)
    validation_case_ids: Mapped[list] = mapped_column(JSONB)
    discovery_sample_ids: Mapped[list] = mapped_column(JSONB)
    validation_sample_ids: Mapped[list] = mapped_column(JSONB)
    discovery_aliquot_ids: Mapped[list] = mapped_column(JSONB)
    validation_aliquot_ids: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_partition_snapshot", "snapshot_id"),
        CheckConstraint(
            "NOT (discovery_case_ids && validation_case_ids)",
            name="ck_partition_case_disjoint",
        ),
    )


# CJ-17: JevService
class JevEvaluation(Base):
    __tablename__ = "jev_evaluations"
    evaluation_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(50))
    subject_type: Mapped[str] = mapped_column(String(50))
    subject_id: Mapped[str] = mapped_column(String(100))
    state_schema: Mapped[str] = mapped_column(String(50))
    state_schema_version: Mapped[str] = mapped_column(String(40))
    state_hash: Mapped[str] = mapped_column(String(71))
    question_set_id: Mapped[str] = mapped_column(String(100))
    question_set_version: Mapped[str] = mapped_column(String(40))
    policy_version: Mapped[str] = mapped_column(String(40))
    requested_model: Mapped[str] = mapped_column(String(100))
    resolved_model: Mapped[str] = mapped_column(String(100))
    sdk_version: Mapped[str] = mapped_column(String(40))
    answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    usage_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    usage_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(30), default="completed")
    error: Mapped[str | None] = mapped_column(Text)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# CJ-19: Discovery
class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"
    discovery_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidate_observations.candidate_id"))
    search_run_id: Mapped[str] = mapped_column(ForeignKey("search_runs.search_run_id"))
    state: Mapped[str] = mapped_column(String(30), default="running")
    expansion_count: Mapped[int] = mapped_column(Integer, default=0)
    jev_evaluation_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    routing_decisions: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_discovery_candidate", "candidate_id"),)


# CJ-20: Reproduction + DiscoveryTrace
class FindingReproduction(Base):
    __tablename__ = "finding_reproductions"
    reproduction_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.finding_id"))
    # IDENTICAL, MISMATCH, FAILED, UNAVAILABLE_VERSION
    status: Mapped[str] = mapped_column(String(30))
    source_hashes: Mapped[dict] = mapped_column(JSONB, default=dict)
    mismatched_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    engine_available: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DiscoveryTrace(Base):
    __tablename__ = "discovery_trace"
    trace_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.finding_id"))
    search_run_id: Mapped[str | None] = mapped_column(ForeignKey("search_runs.search_run_id"))
    candidate_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    jev_evaluation_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    expansion_recipe_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    routing_summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
