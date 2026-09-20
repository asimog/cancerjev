import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"
    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None]


class DatasetSnapshot(Base):
    __tablename__ = "dataset_snapshots"
    snapshot_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    snapshot_hash: Mapped[str] = mapped_column(String(71), unique=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"))
    provenance: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DatasetObject(Base):
    __tablename__ = "dataset_objects"
    sha256: Mapped[str] = mapped_column(String(71), primary_key=True)
    size: Mapped[int] = mapped_column(BigInteger)
    media_type: Mapped[str] = mapped_column(String(100))


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
    state: Mapped[str] = mapped_column(String(30))
    parameters: Mapped[dict] = mapped_column(JSONB)


class Finding(Base):
    __tablename__ = "findings"
    finding_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.analysis_id"))
    payload: Mapped[dict] = mapped_column(JSONB)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Cohort(Base):
    __tablename__ = "cohorts"
    cohort_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("dataset_snapshots.snapshot_id"))
    definition: Mapped[dict] = mapped_column(JSONB)
    case_ids: Mapped[list] = mapped_column(JSONB)
    sample_ids: Mapped[list] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(71), unique=True)
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
    __table_args__ = (Index("ix_jobs_claim", "state", "job_type", "created_at"),)


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
