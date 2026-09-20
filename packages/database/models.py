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
    state: Mapped[str] = mapped_column(String(30))
    parameters: Mapped[dict] = mapped_column(JSONB)
    expected_input_artifacts: Mapped[list[str]] = mapped_column(JSONB, default=list)
    input_materializations: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.job_id"), unique=True)
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
