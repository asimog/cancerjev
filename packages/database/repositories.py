import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.database.models import (
    Analysis,
    AuditEvent,
    Cohort,
    DatasetObject,
    DatasetSnapshot,
    Finding,
    IdempotencyRecord,
    Job,
    Materialization,
    MaterializationSource,
    Project,
    SnapshotArtifact,
)


class _Repository:
    def __init__(self, session: Session):
        self.session = session

    def _save(self, value):
        self.session.add(value)
        self.session.flush()
        return value


class SqlProjectRepository(_Repository):
    def get(self, project_id: str) -> Project | None:
        return self.session.get(Project, project_id)

    def list(self, *, limit: int, offset: int) -> list[Project]:
        return list(
            self.session.scalars(
                select(Project).order_by(Project.project_id).offset(offset).limit(limit)
            )
        )

    def save(self, project: Project) -> Project:
        existing = self.get(project.project_id)
        if existing:
            existing.name = project.name
            existing.primary_site = project.primary_site
            self.session.flush()
            return existing
        try:
            with self.session.begin_nested():
                return self._save(project)
        except IntegrityError:
            existing = self.get(project.project_id)
            if existing is None:
                raise
            return existing


class SqlArtifactRepository(_Repository):
    def by_snapshot_role(self, snapshot_id: str) -> dict[str, DatasetObject]:
        rows = self.session.execute(
            select(SnapshotArtifact.logical_role, DatasetObject)
            .join(DatasetObject, DatasetObject.sha256 == SnapshotArtifact.sha256)
            .where(SnapshotArtifact.snapshot_id == snapshot_id)
        )
        return dict(rows.all())

    def get(self, sha256: str) -> DatasetObject | None:
        return self.session.get(DatasetObject, sha256)

    def save(self, artifact: DatasetObject) -> DatasetObject:
        existing = self.get(artifact.sha256)
        if existing:
            if existing.size != artifact.size:
                raise ValueError("artifact hash already exists with a different byte size")
            return existing
        try:
            with self.session.begin_nested():
                return self._save(artifact)
        except IntegrityError:
            existing = self.get(artifact.sha256)
            if existing is None:
                raise
            return existing

    def list_for_snapshot(self, snapshot_id: str) -> list[DatasetObject]:
        return list(
            self.session.scalars(
                select(DatasetObject)
                .join(SnapshotArtifact, SnapshotArtifact.sha256 == DatasetObject.sha256)
                .where(SnapshotArtifact.snapshot_id == snapshot_id)
                .order_by(SnapshotArtifact.logical_role)
            )
        )


class SqlMaterializationRepository(_Repository):
    def get(self, materialization_id: str) -> Materialization | None:
        return self.session.get(Materialization, materialization_id)

    def get_source(self, source_id: str) -> MaterializationSource | None:
        return self.session.get(MaterializationSource, source_id)

    def list(self, snapshot_id: str, modality: str, measurement_type: str) -> list[Materialization]:
        return list(
            self.session.scalars(
                select(Materialization)
                .where(
                    Materialization.snapshot_id == snapshot_id,
                    Materialization.modality == modality,
                    Materialization.measurement_type == measurement_type,
                )
                .order_by(Materialization.materialization_id)
            )
        )


class SqlSnapshotRepository(_Repository):
    def get(self, snapshot_id: str) -> DatasetSnapshot | None:
        return self.session.get(DatasetSnapshot, snapshot_id)

    def list(self, *, project_id: str | None, limit: int, offset: int) -> list[DatasetSnapshot]:
        statement = select(DatasetSnapshot)
        if project_id:
            statement = statement.where(DatasetSnapshot.project_id == project_id)
        return list(
            self.session.scalars(
                statement.order_by(DatasetSnapshot.created_at, DatasetSnapshot.snapshot_id)
                .offset(offset)
                .limit(limit)
            )
        )

    def save(self, snapshot: DatasetSnapshot) -> DatasetSnapshot:
        existing = self.get(snapshot.snapshot_id)
        if existing:
            return self._validate_existing(existing, snapshot)
        try:
            with self.session.begin_nested():
                return self._save(snapshot)
        except IntegrityError:
            existing = self.get(snapshot.snapshot_id)
            if existing is None:
                raise
            return self._validate_existing(existing, snapshot)

    @staticmethod
    def _validate_existing(
        existing: DatasetSnapshot, requested: DatasetSnapshot
    ) -> DatasetSnapshot:
        if existing.snapshot_hash != requested.snapshot_hash:
            raise ValueError("snapshot ID already exists with a different logical hash")
        existing_artifacts = (
            existing.manifest_sha256,
            existing.coverage_sha256,
            existing.identity_sha256,
            existing.provenance_sha256,
        )
        requested_artifacts = (
            requested.manifest_sha256,
            requested.coverage_sha256,
            requested.identity_sha256,
            requested.provenance_sha256,
        )
        if existing_artifacts != requested_artifacts:
            raise ValueError("published snapshot artifact identity cannot be changed")
        return existing


class SqlCohortRepository(_Repository):
    def get(self, cohort_id: str) -> Cohort | None:
        return self.session.get(Cohort, cohort_id)

    def by_hash(self, content_hash: str) -> Cohort | None:
        return self.session.scalar(select(Cohort).where(Cohort.content_hash == content_hash))

    def list(self, *, snapshot_id: str | None, limit: int, offset: int) -> list[Cohort]:
        statement = select(Cohort)
        if snapshot_id:
            statement = statement.where(Cohort.snapshot_id == snapshot_id)
        return list(
            self.session.scalars(
                statement.order_by(Cohort.created_at, Cohort.cohort_id).offset(offset).limit(limit)
            )
        )

    def save(self, cohort: Cohort) -> Cohort:
        existing = self.by_hash(cohort.content_hash)
        if existing:
            return existing
        try:
            with self.session.begin_nested():
                return self._save(cohort)
        except IntegrityError:
            existing = self.by_hash(cohort.content_hash)
            if existing is None:
                raise
            return existing


class SqlAnalysisRepository(_Repository):
    def get(self, analysis_id: str | uuid.UUID) -> Analysis | None:
        return self.session.get(Analysis, uuid.UUID(str(analysis_id)))

    def list(
        self, *, snapshot_id: str | None, state: str | None, limit: int, offset: int
    ) -> list[Analysis]:
        statement = select(Analysis)
        if snapshot_id:
            statement = statement.where(Analysis.snapshot_id == snapshot_id)
        if state:
            statement = statement.where(Analysis.state == state)
        return list(
            self.session.scalars(
                statement.order_by(Analysis.created_at, Analysis.analysis_id)
                .offset(offset)
                .limit(limit)
            )
        )

    def save(self, analysis: Analysis) -> Analysis:
        return self._save(analysis)


class SqlFindingRepository(_Repository):
    def get(self, finding_id: str) -> Finding | None:
        return self.session.get(Finding, finding_id)

    def list(
        self,
        *,
        snapshot_id: str | None,
        cohort_id: str | None,
        analysis_id: str | None,
        finding_type: str | None,
        gene: str | None,
        result_hash: str | None,
        limit: int,
        offset: int,
    ) -> list[Finding]:
        statement = select(Finding)
        for value, column in (
            (snapshot_id, Finding.snapshot_id),
            (cohort_id, Finding.cohort_id),
            (finding_type, Finding.finding_type),
            (gene, Finding.gene_symbol),
            (result_hash, Finding.result_hash),
        ):
            if value:
                statement = statement.where(column == value)
        if analysis_id:
            statement = statement.where(Finding.analysis_id == uuid.UUID(analysis_id))
        return list(
            self.session.scalars(
                statement.order_by(Finding.created_at, Finding.finding_id)
                .offset(offset)
                .limit(limit)
            )
        )

    def save(self, finding: Finding) -> Finding:
        existing = self.get(finding.finding_id)
        if existing:
            if existing.result_hash != finding.result_hash:
                raise ValueError("finding ID already exists with another result hash")
            return existing
        return self._save(finding)


class SqlAuditRepository(_Repository):
    def append(self, event: AuditEvent) -> AuditEvent:
        return self._save(event)


class SqlJobRepository(_Repository):
    def save(self, job: Job) -> Job:
        return self._save(job)


class SqlIdempotencyRepository(_Repository):
    def get(self, scope: str, key: str) -> IdempotencyRecord | None:
        return self.session.get(IdempotencyRecord, (scope, key))

    def reserve(
        self, *, scope: str, key: str, request_hash: str, resource_type: str, resource_id: str
    ) -> tuple[IdempotencyRecord, bool]:
        record = IdempotencyRecord(
            scope=scope,
            idempotency_key=key,
            request_hash=request_hash,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        try:
            with self.session.begin_nested():
                self._save(record)
            return record, True
        except IntegrityError:
            existing = self.get(scope, key)
            if existing is None:
                raise
            return existing, False
