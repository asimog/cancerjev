import json
import tempfile
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.database.models import (
    Analysis,
    AuditEvent,
    Cohort,
    DatasetObject,
    DatasetSnapshot,
    Finding,
    Job,
    Materialization,
    MaterializationSource,
    Project,
    SnapshotArtifact,
)
from packages.database.repositories import (
    SqlAnalysisRepository,
    SqlArtifactRepository,
    SqlAuditRepository,
    SqlCohortRepository,
    SqlFindingRepository,
    SqlIdempotencyRepository,
    SqlJobRepository,
    SqlMaterializationRepository,
    SqlProjectRepository,
    SqlSnapshotRepository,
)
from packages.gdc.policy import official_api, require_open
from packages.provenance.hashing import canonical_hash
from packages.resources.snapshots import FrozenSnapshotReader
from packages.schemas.finding import Finding as FindingPayload
from packages.schemas.resources import (
    AnalysisCreate,
    ArtifactRegistration,
    CohortCreate,
)
from packages.schemas.snapshot import SnapshotRecord
from packages.statistics.registry import resolve_engine
from packages.storage.config import StorageSettings
from scientific.crossmodal.analysis import EngineContext, result_identity, runtime_environment


class ResourceNotFoundError(LookupError):
    pass


class ResourceConflictError(RuntimeError):
    pass


class InvalidTransitionError(ResourceConflictError):
    pass


ANALYSIS_TRANSITIONS = {
    "requested": {"queued", "cancelled"},
    "queued": {"running", "failed", "cancelled"},
    "running": {"completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


class DurableResourceService:
    """Transactional application boundary for durable metadata resources."""

    def __init__(self, session: Session, *, storage_settings: StorageSettings | None = None):
        self.session = session
        self.storage_settings = storage_settings or StorageSettings()
        self.projects = SqlProjectRepository(session)
        self.artifacts = SqlArtifactRepository(session)
        self.snapshots = SqlSnapshotRepository(session)
        self.cohorts = SqlCohortRepository(session)
        self.analyses = SqlAnalysisRepository(session)
        self.findings = SqlFindingRepository(session)
        self.audit = SqlAuditRepository(session)
        self.jobs = SqlJobRepository(session)
        self.idempotency = SqlIdempotencyRepository(session)
        self.materializations = SqlMaterializationRepository(session)

    def save_project(
        self, project_id: str, *, name: str | None = None, primary_site: list[str] | None = None
    ) -> Project:
        return self.projects.save(
            Project(project_id=project_id, name=name, primary_site=sorted(set(primary_site or [])))
        )

    def register_artifact(self, value: ArtifactRegistration) -> DatasetObject:
        return self.artifacts.save(DatasetObject(**value.model_dump()))

    def register_snapshot(
        self, snapshot: SnapshotRecord, artifacts: list[ArtifactRegistration]
    ) -> DatasetSnapshot:
        official_api(snapshot.source_api)
        for item in snapshot.objects:
            require_open(item.access)
        self.save_project(snapshot.project_id)
        by_role = {
            artifact.logical_role: self.register_artifact(artifact) for artifact in artifacts
        }
        record = DatasetSnapshot(
            snapshot_id=snapshot.snapshot_id,
            snapshot_hash=snapshot.snapshot_hash,
            project_id=snapshot.project_id,
            status="published",
            source_api=snapshot.source_api,
            gdc_release=snapshot.gdc_release,
            schema_versions=snapshot.canonical_schema_versions,
            policy_versions={
                "transformation": snapshot.transformation_version,
                "normalization": snapshot.normalization_metadata,
            },
            identity_version=snapshot.identity_version,
            manifest_sha256=_role_hash(by_role, "manifest"),
            coverage_sha256=_role_hash(by_role, "coverage"),
            identity_sha256=_role_hash(by_role, "identity_links"),
            provenance_sha256=_role_hash(by_role, "provenance"),
            provenance=snapshot.upstream_provenance,
            created_at=snapshot.created_at,
            published_at=datetime.now(UTC),
        )
        existing = self.snapshots.get(snapshot.snapshot_id)
        saved = self.snapshots.save(record)
        for role, artifact in by_role.items():
            key = (saved.snapshot_id, role)
            link = self.session.get(SnapshotArtifact, key)
            if link and link.sha256 != artifact.sha256:
                raise ResourceConflictError(f"published snapshot artifact role changed: {role}")
            if link is None:
                self.session.add(
                    SnapshotArtifact(
                        snapshot_id=saved.snapshot_id,
                        logical_role=role,
                        sha256=artifact.sha256,
                    )
                )
        self.session.flush()
        if existing is None:
            self._audit("snapshot.registered", "snapshot", saved.snapshot_id)
        return saved

    def snapshot_artifacts(self, snapshot_id: str) -> dict[str, DatasetObject]:
        if self.snapshots.get(snapshot_id) is None:
            raise ResourceNotFoundError("snapshot not found")
        return self.artifacts.by_snapshot_role(snapshot_id)

    def get_source(self, source_id: str) -> MaterializationSource:
        value = self.materializations.get_source(source_id)
        if value is None:
            raise ResourceNotFoundError("materialization source not found")
        return value

    def register_source(
        self,
        *,
        snapshot_id: str,
        artifact: ArtifactRegistration,
        source_file_id: str | None,
        source_metadata: dict,
    ) -> MaterializationSource:
        if self.snapshots.get(snapshot_id) is None:
            raise ResourceNotFoundError("snapshot not found")
        identity = {
            "snapshot_id": snapshot_id,
            "sha256": artifact.sha256,
            "source_file_id": source_file_id,
            "source_metadata": source_metadata,
        }
        source_id = canonical_hash(
            {
                "snapshot_id": snapshot_id,
                "sha256": artifact.sha256,
                "source_file_id": source_file_id,
                "kind": source_metadata.get("kind"),
            }
        )
        existing = self.materializations.get_source(source_id)
        if existing:
            return existing
        self.register_artifact(artifact)
        try:
            with self.session.begin_nested():
                value = MaterializationSource(source_id=source_id, **identity)
                self.session.add(value)
                self.session.flush()
        except IntegrityError:
            existing = self.materializations.get_source(source_id)
            if existing is None:
                raise
            return existing
        self._audit("materialization.source_registered", "source", source_id)
        return value

    def get_materialization(self, materialization_id: str) -> Materialization | None:
        return self.materializations.get(materialization_id)

    def list_materializations(
        self, snapshot_id: str, modality: str, measurement_type: str = ""
    ) -> list[Materialization]:
        return self.materializations.list(snapshot_id, modality, measurement_type)

    def register_materialization(
        self, *, metadata: dict, output: ArtifactRegistration, diagnostics: ArtifactRegistration
    ) -> Materialization:
        source = self.get_source(metadata["source_id"])
        if source.snapshot_id != metadata["snapshot_id"]:
            raise ResourceConflictError("source does not belong to snapshot")
        if metadata["output_sha256"] != output.sha256 or (
            metadata["diagnostics_sha256"] != diagnostics.sha256
        ):
            raise ResourceConflictError("materialization artifact mismatch")
        existing = self.get_materialization(metadata["materialization_id"])
        if existing:
            if existing.logical_sha256 != metadata["logical_sha256"]:
                raise ResourceConflictError("materialization logical content changed")
            return existing
        # Race winner registers its objects and link in the same savepoint.
        try:
            with self.session.begin_nested():
                self.register_artifact(output)
                self.register_artifact(diagnostics)
                value = Materialization(**metadata)
                self.session.add(value)
                self.session.flush()
                self.session.add(
                    SnapshotArtifact(
                        snapshot_id=value.snapshot_id,
                        logical_role="materialization:" + value.materialization_id,
                        sha256=output.sha256,
                    )
                )
                self._audit(
                    "materialization.completed", "materialization", value.materialization_id
                )
                self.session.flush()
        except IntegrityError:
            existing = self.get_materialization(metadata["materialization_id"])
            if existing is None:
                raise
            if existing.logical_sha256 != metadata["logical_sha256"]:
                raise ResourceConflictError("materialization logical content changed") from None
            return existing
        return value

    def create_cohort(self, request: CohortCreate) -> Cohort:
        if self.snapshots.get(request.snapshot_id) is None:
            raise ResourceNotFoundError("snapshot not found")
        self.validate_cohort_membership(request.snapshot_id, request.case_ids, request.sample_ids)
        identity = {
            "snapshot_id": request.snapshot_id,
            "definition_version": request.definition_version,
            "definition": request.definition,
            "case_ids": sorted(set(request.case_ids)),
            "sample_ids": sorted(set(request.sample_ids)),
            "exclusion_reasons": request.exclusion_reasons,
            "selection_policy_version": request.selection_policy_version,
        }
        digest = canonical_hash(identity)
        existing = self.cohorts.by_hash(digest)
        if existing:
            return existing
        cohort = self.cohorts.save(
            Cohort(
                cohort_id=f"CO-{digest.removeprefix('sha256:')[:16]}",
                snapshot_id=request.snapshot_id,
                definition_version=request.definition_version,
                definition=request.definition,
                case_ids=identity["case_ids"],
                sample_ids=identity["sample_ids"],
                exclusion_reasons=request.exclusion_reasons,
                selection_policy_version=request.selection_policy_version,
                content_hash=digest,
            )
        )
        self._audit("cohort.created", "cohort", cohort.cohort_id)
        return cohort

    def validate_cohort_membership(
        self, snapshot_id: str, case_ids: list[str], sample_ids: list[str]
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="cancerjev-cohort-") as tmp:
            _, graph = self.snapshot_reader().load(snapshot_id, Path(tmp))
        cases = set(case_ids)
        samples = {sample.sample_id: sample.case_id for sample in graph.samples}
        if not cases.issubset(graph.case_ids):
            raise ResourceConflictError("cohort cases are not members of the frozen snapshot")
        if not set(sample_ids).issubset(samples):
            raise ResourceConflictError("cohort samples are not members of the frozen snapshot")
        if any(samples[sample] not in cases for sample in sample_ids):
            raise ResourceConflictError("cohort sample does not belong to a selected case")

    def snapshot_reader(self) -> FrozenSnapshotReader:
        return FrozenSnapshotReader(self, self.storage_settings.store(), self.storage_settings)

    async def manifest(self, snapshot_id: str, client, file_ids: list[str] | None = None) -> bytes:
        with tempfile.TemporaryDirectory(prefix="cancerjev-manifest-") as tmp:
            snapshot, _ = self.snapshot_reader().load(snapshot_id, Path(tmp))
        return await client.manifest(snapshot, file_ids)

    def create_analysis(self, request: AnalysisCreate, idempotency_key: str) -> Analysis:
        _reject_matrix_payload(request.parameters)
        snapshot = self.snapshots.get(request.snapshot_id)
        cohort = self.cohorts.get(request.cohort_id)
        if snapshot is None or cohort is None or cohort.snapshot_id != snapshot.snapshot_id:
            raise ResourceNotFoundError("snapshot/cohort combination not found")
        self.validate_cohort_membership(snapshot.snapshot_id, cohort.case_ids, cohort.sample_ids)
        resolved_hashes = set()
        inputs = {}
        for expected in request.input_materializations:
            value = self.get_materialization(expected.materialization_id)
            if value is None:
                raise ResourceNotFoundError("input materialization not found")
            if (
                value.snapshot_id != request.snapshot_id
                or value.modality != expected.modality
                or value.measurement_type != expected.measurement_type
            ):
                raise ResourceConflictError(
                    "input materialization snapshot/modality/measurement mismatch"
                )
            inputs[expected.materialization_id] = expected.model_dump(mode="json")
            resolved_hashes.add(value.output_sha256)
        try:
            spec = resolve_engine(request.engine, request.engine_version)
        except ValueError:
            # Unsupported engines retain the existing durable-failure behavior:
            # the worker records UNSUPPORTED_ENGINE_OR_VERSION.
            spec = None
        if spec is not None:
            by_modality = {}
            for expected in request.input_materializations:
                if expected.modality in by_modality:
                    raise ResourceConflictError(
                        f"engine requires exactly one {expected.modality} materialization"
                    )
                by_modality[expected.modality] = expected
            if set(by_modality) != set(spec.modalities):
                raise ResourceConflictError(
                    f"engine requires exactly one input for modalities {spec.modalities}"
                )
            for modality, measurement_type in zip(
                spec.modalities, spec.measurement_types, strict=True
            ):
                if by_modality[modality].measurement_type != measurement_type:
                    raise ResourceConflictError(
                        f"engine requires {modality} measurement {measurement_type!r}"
                    )
        if (
            request.expected_input_artifacts
            and set(request.expected_input_artifacts) != resolved_hashes
        ):
            raise ResourceConflictError("input hashes do not match resolved materializations")
        request_hash = canonical_hash(request.model_dump(mode="json"))
        analysis_id = uuid.uuid4()
        reservation, created = self.idempotency.reserve(
            scope="analysis.create",
            key=idempotency_key,
            request_hash=request_hash,
            resource_type="analysis",
            resource_id=str(analysis_id),
        )
        if not created:
            if reservation.request_hash != request_hash:
                raise ResourceConflictError("idempotency key was used for a different request")
            existing = self.analyses.get(reservation.resource_id)
            if existing is None:
                raise ResourceConflictError("idempotent analysis outcome is unavailable")
            return existing
        job_id = uuid.uuid4()
        job = self.jobs.save(
            Job(
                job_id=job_id,
                job_type="run_analysis_from_artifacts",
                state="queued",
                payload={"analysis_id": str(analysis_id)},
                max_attempts=3,
            )
        )
        analysis = self.analyses.save(
            Analysis(
                analysis_id=analysis_id,
                snapshot_id=request.snapshot_id,
                cohort_id=request.cohort_id,
                engine=request.engine,
                engine_version=request.engine_version,
                parameters=request.parameters,
                expected_input_artifacts=sorted(resolved_hashes),
                input_materializations=[inputs[key] for key in sorted(inputs)],
                state="queued",
                job_id=job.job_id,
                queued_at=datetime.now(UTC),
            )
        )
        reservation.resource_id = str(analysis.analysis_id)
        self._audit("analysis.requested", "analysis", str(analysis.analysis_id))
        self._audit(
            "job.queued", "job", str(job.job_id), {"analysis_id": str(analysis.analysis_id)}
        )
        return analysis

    def transition_analysis(
        self, analysis_id: str, state: str, *, error: str | None = None
    ) -> Analysis:
        analysis = self.analyses.get(analysis_id)
        if analysis is None:
            raise ResourceNotFoundError("analysis not found")
        if state not in ANALYSIS_TRANSITIONS.get(analysis.state, set()):
            raise InvalidTransitionError(f"cannot transition {analysis.state} to {state}")
        analysis.state = state
        now = datetime.now(UTC)
        if state == "running":
            analysis.started_at = now
        if state in {"completed", "failed", "cancelled"}:
            analysis.completed_at = now
        analysis.error = error[:8000] if error else None
        self.session.flush()
        if state in {"completed", "failed"}:
            self._audit(f"analysis.{state}", "analysis", str(analysis.analysis_id))
        return analysis

    def publish_findings(
        self, analysis: Analysis, findings: Sequence[FindingPayload]
    ) -> list[Finding]:
        """Server-owned publication of computed scientific payloads.

        Finding identity is recomputed here from persisted scientific context
        and deterministic outputs; callers can never supply authoritative IDs,
        versions, input hashes, tested universes, or result hashes. Concurrent
        attempts converge on the unique
        (analysis_id, result_hash) publication instead of duplicating rows.
        """
        if analysis.state != "running":
            raise ResourceConflictError("finding publication requires a running analysis")
        snapshot = self.snapshots.get(analysis.snapshot_id)
        cohort = self.cohorts.get(analysis.cohort_id) if analysis.cohort_id else None
        if snapshot is None or cohort is None:
            raise ResourceConflictError("finding publication context is unavailable")
        try:
            spec = resolve_engine(analysis.engine, analysis.engine_version)
        except ValueError as exc:
            raise ResourceConflictError(str(exc)) from exc
        context = EngineContext(
            snapshot_id=analysis.snapshot_id,
            snapshot_hash=snapshot.snapshot_hash,
            cohort_id=analysis.cohort_id,
            cohort_content_hash=cohort.content_hash,
            cohort_size=len(cohort.case_ids),
            engine_version=analysis.engine_version,
            method_version=spec.method_version,
            parameters=dict(analysis.parameters),
            input_hashes=tuple(sorted(analysis.expected_input_artifacts)),
            environment=runtime_environment(),
        )
        tested_gene_ids = tuple(sorted(finding.gene for finding in findings))
        if len(set(tested_gene_ids)) != len(tested_gene_ids):
            raise ResourceConflictError("duplicate finding gene in one tested universe")
        published: list[Finding] = []
        for finding in findings:
            authoritative = self._attest_finding(
                finding,
                context=context,
                cohort=cohort,
                tested_gene_ids=tested_gene_ids,
            )
            finding_id = "F-" + canonical_hash(
                {
                    "analysis_id": str(analysis.analysis_id),
                    "result_hash": authoritative.result_hash,
                }
            ).removeprefix("sha256:")[:32]
            published.append(
                self.findings.save(
                    Finding(
                        finding_id=finding_id,
                        analysis_id=analysis.analysis_id,
                        snapshot_id=analysis.snapshot_id,
                        cohort_id=analysis.cohort_id,
                        finding_type=authoritative.finding_type,
                        gene_id=authoritative.gene,
                        gene_symbol=None,
                        analysis_version=authoritative.analysis_version,
                        result_hash=authoritative.result_hash,
                        payload=authoritative.model_dump(mode="json"),
                    )
                )
            )
        for row in published:
            self._audit("finding.published", "finding", row.finding_id)
        return published

    @staticmethod
    def _attest_finding(
        finding: FindingPayload,
        *,
        context: EngineContext,
        cohort: Cohort,
        tested_gene_ids: tuple[str, ...],
    ) -> FindingPayload:
        eligible_cases = tuple(sorted(set(finding.eligible_case_ids)))
        eligible_samples = tuple(sorted(set(finding.eligible_sample_ids)))
        if not set(eligible_cases).issubset(cohort.case_ids) or not set(
            eligible_samples
        ).issubset(cohort.sample_ids):
            raise ResourceConflictError("finding eligibility exceeds the frozen cohort")
        if finding.eligible_cases != len(eligible_cases):
            raise ResourceConflictError("finding eligible case count is inconsistent")
        if finding.n_effective != len(eligible_samples):
            raise ResourceConflictError("finding effective sample count is inconsistent")
        missing_n = context.cohort_size - len(eligible_cases)
        missing_fraction = missing_n / context.cohort_size if context.cohort_size else 0
        payload = {
            "effect_size": finding.effect_size,
            "p_value": finding.p_value,
            "q_value": finding.q_value,
            "confidence_interval": list(finding.confidence_interval)
            if finding.confidence_interval is not None
            else None,
            "n_effective": finding.n_effective,
            "eligible_case_ids": list(eligible_cases),
            "eligible_sample_ids": list(eligible_samples),
            "missing_n": missing_n,
        }
        if payload["confidence_interval"] is None:
            raise ResourceConflictError("finding confidence interval is required")
        computed_hash = result_identity(
            context,
            finding.gene,
            payload,
            tested_gene_ids,
        )
        return finding.model_copy(
            update={
                "snapshot_id": context.snapshot_id,
                "cohort_size": context.cohort_size,
                "eligible_cases": len(eligible_cases),
                "eligible_case_ids": eligible_cases,
                "eligible_sample_ids": eligible_samples,
                "missing_n": missing_n,
                "missing_fraction": missing_fraction,
                "analysis_version": context.method_version,
                "input_object_hashes": tuple(sorted(context.input_hashes)),
                "tested_gene_ids": tested_gene_ids,
                "result_hash": computed_hash,
            }
        )

    def _audit(
        self,
        event_type: str,
        resource_type: str,
        resource_id: str,
        context: dict | None = None,
    ) -> AuditEvent:
        return self.audit.append(
            AuditEvent(
                event_type=event_type,
                detail="",
                actor_id="system",
                resource_type=resource_type,
                resource_id=resource_id,
                context=context or {},
            )
        )


def _role_hash(artifacts: dict[str, DatasetObject], role: str) -> str | None:
    artifact = artifacts.get(role)
    return artifact.sha256 if artifact else None


def _reject_matrix_payload(value: dict) -> None:
    if len(json.dumps(value, separators=(",", ":"))) > 65_536:
        raise ValueError("metadata payload exceeds 64 KiB; store scientific data as an artifact")
    forbidden = {"matrix", "molecular_matrix", "expression_rows", "mutation_rows", "cnv_rows"}
    if forbidden.intersection(value):
        raise ValueError("genome-scale molecular data must be stored as immutable artifacts")
