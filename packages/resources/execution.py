"""Narrow artifact execution: resolve, verify, compute, and publish fenced.

The service never receives molecular data in a payload, never contacts GDC,
and never holds database locks while computing. Job ownership is proven with
``job_id + worker_id + attempt_token`` around each transaction; deterministic
failures carry bounded reason codes the worker records on the job.
"""

import tempfile
from pathlib import Path

import pyarrow.parquet as pq
from sqlalchemy.orm import Session

from packages.database.config import resolve_database_url
from packages.database.jobs import (
    ClaimedJob,
    JobStateError,
    LeaseLostError,
    verify_lease,
)
from packages.database.session import session_factory
from packages.resources.service import DurableResourceService
from packages.resources.snapshots import FrozenSnapshotReader
from packages.schemas.finding import Finding
from packages.statistics.registry import EngineSpec, resolve_engine
from packages.storage.config import StorageSettings
from packages.storage.objects import (
    ObjectStore,
    ObjectStoreError,
    ObjectStorePermissionError,
    ObjectStoreServiceError,
)
from scientific.crossmodal.analysis import EngineContext, runtime_environment

#: Identity columns every canonical molecular parquet must expose per modality.
REQUIRED_COLUMNS = {
    "cnv": ("case_id", "sample_id", "gene_id", "cnv_value"),
    "expression": ("case_id", "sample_id", "gene_id", "value"),
}


class ExecutionFailure(Exception):
    """Deterministic failure with a bounded reason code recorded on the job."""

    retryable: bool = False
    failure_reason: str = "INVALID_SCIENTIFIC_INPUT"


class UnsupportedEngine(ExecutionFailure):
    failure_reason = "UNSUPPORTED_ENGINE_OR_VERSION"


class IntegrityFailure(ExecutionFailure):
    failure_reason = "INTEGRITY_FAILURE"


class TransientInfrastructure(ExecutionFailure):
    retryable = True
    failure_reason = "TRANSIENT_INFRASTRUCTURE"


def _guarded_artifact_operation(label: str, operation):
    """Translate object-store and frozen-graph failures into bounded reasons.

    Missing, unreadable, tampered, or backend-mismatched bytes must fail as
    deterministic integrity or transient infrastructure, never as a raw
    ``FileNotFoundError``/``ValueError`` the worker cannot classify.
    """
    try:
        return operation()
    except ObjectStoreServiceError as exc:
        raise TransientInfrastructure(str(exc)) from exc
    except (
        ObjectStorePermissionError,
        ObjectStoreError,
        FileNotFoundError,
        ValueError,
    ) as exc:
        raise IntegrityFailure(f"{label}: {exc}") from exc


class AnalysisExecutionService:
    def __init__(self, session: Session, store: ObjectStore):
        self.session = session
        self.store = store
        self.settings = StorageSettings()
        self.resources = DurableResourceService(session)
        self.reader = FrozenSnapshotReader(self.resources, store, self.settings)

    @classmethod
    def run_claimed(cls, claimed: ClaimedJob) -> dict:
        """Worker entry point: independent sessions per phase, fenced by the claim."""
        analysis_id = claimed.payload.get("analysis_id")
        if not isinstance(analysis_id, str) or not analysis_id:
            raise ExecutionFailure("job payload lacks a durable analysis_id reference")
        factory = session_factory(resolve_database_url())
        settings = StorageSettings()
        store = settings.store()
        try:
            return cls._run_phases(claimed, factory, store, analysis_id)
        except (LeaseLostError, JobStateError):
            # A faster attempt may have published and succeeded while we ran.
            return cls._converged_result(factory, analysis_id)

    @classmethod
    def _run_phases(cls, claimed, factory, store, analysis_id: str) -> dict:
        # Phase 1: fenced transition of the analysis to running (short transaction).
        with factory.begin() as session:
            verify_lease(session, claimed.job_id, claimed.worker_id, claimed.attempt_token)
            analysis = cls._activate(session, analysis_id)
            if analysis.state == "completed":
                return cls._completed_result(session, analysis)
            frozen = _FrozenAnalysis.from_row(analysis)

        # Phase 2: deterministic compute outside every transaction.
        findings = cls._compute(factory, store, frozen)

        # Phase 3: fenced publication of immutable findings (short transaction).
        with factory.begin() as session:
            verify_lease(session, claimed.job_id, claimed.worker_id, claimed.attempt_token)
            analysis = DurableResourceService(session).analyses.get(analysis_id)
            if analysis is None:
                raise IntegrityFailure("analysis vanished during execution")
            if analysis.state == "completed":
                return cls._completed_result(session, analysis)
            if analysis.state != "running":
                raise ExecutionFailure(
                    f"analysis in state {analysis.state} cannot publish findings"
                )
            published = DurableResourceService(session).publish_findings(analysis, findings)
            DurableResourceService(session).transition_analysis(analysis_id, "completed")
            return {
                "analysis_id": analysis_id,
                "published": len(published),
                "finding_ids": [row.finding_id for row in published],
                "converged": False,
            }

    @staticmethod
    def _activate(session: Session, analysis_id: str):
        service = DurableResourceService(session)
        analysis = service.analyses.get(analysis_id)
        if analysis is None:
            raise IntegrityFailure("analysis not found")
        if analysis.state in {"queued", "requested"}:
            service.transition_analysis(analysis_id, "running")
        elif analysis.state not in {"running", "completed"}:
            raise ExecutionFailure(f"analysis in state {analysis.state} cannot run")
        return analysis

    @classmethod
    def _compute(cls, factory, store: ObjectStore, frozen: "_FrozenAnalysis") -> list[Finding]:
        try:
            spec = resolve_engine(frozen.engine, frozen.engine_version)
        except ValueError as exc:
            raise UnsupportedEngine(str(exc)) from exc
        cohort = cls._cohort(factory, store, frozen)
        with tempfile.TemporaryDirectory(prefix="cancerjev-execute-") as tmp:
            staged = cls._stage_inputs(factory, store, frozen, spec, Path(tmp))
            rows_by_modality = {
                modality: cls._cohort_rows(cls._read_rows(path, modality), cohort)
                for modality, path in staged.items()
            }
        engine_context = frozen.engine_context(cohort, spec)
        return spec.run(
            engine_context,
            **dict(zip(spec.inputs, [rows_by_modality[m] for m in spec.modalities], strict=True)),
        )

    @staticmethod
    def _stage_inputs(
        factory, store: ObjectStore, frozen: "_FrozenAnalysis", spec: EngineSpec, tmp: Path
    ) -> dict[str, Path]:
        with factory() as session:
            service = DurableResourceService(session)
            resolved = []
            for expected in frozen.input_materializations:
                materialization = service.get_materialization(expected["materialization_id"])
                if materialization is None:
                    raise IntegrityFailure(
                        f"input materialization not found: {expected['materialization_id']}"
                    )
                if (
                    materialization.snapshot_id != frozen.snapshot_id
                    or materialization.modality != expected["modality"]
                    or materialization.measurement_type != expected["measurement_type"]
                ):
                    raise IntegrityFailure(
                        "input materialization drifted from the frozen analysis contract"
                    )
                resolved.append(
                    (
                        materialization.modality,
                        materialization.measurement_type,
                        materialization.output_sha256,
                    )
                )
            if sorted(frozen.expected_input_artifacts) != sorted(
                digest for _, _, digest in resolved
            ):
                raise IntegrityFailure("resolved artifacts do not match the frozen contract")
            if len(resolved) != len(spec.modalities) or {
                modality for modality, _, _ in resolved
            } != set(spec.modalities):
                raise ExecutionFailure(
                    f"engine {spec.engine} requires exactly one input for {spec.modalities}"
                )
            by_modality = {
                modality: (measurement, digest)
                for modality, measurement, digest in resolved
            }
            for modality, measurement in zip(
                spec.modalities, spec.measurement_types, strict=True
            ):
                if by_modality[modality][0] != measurement:
                    raise ExecutionFailure(
                        f"engine {spec.engine} requires {modality} measurement {measurement!r}"
                    )
            reader = FrozenSnapshotReader(service, store, StorageSettings())
            paths = {}
            for modality in spec.modalities:
                digest = by_modality[modality][1]
                artifact = service.artifacts.get(digest)
                if artifact is None:
                    raise IntegrityFailure(f"input artifact not registered: {digest}")
                destination = tmp / (modality + ".parquet")
                _guarded_artifact_operation(
                    "input artifact unusable",
                    lambda artifact=artifact, destination=destination: reader.stage(
                        artifact, destination
                    ),
                )
                paths[modality] = destination
        return paths

    @staticmethod
    def _read_rows(path: Path, modality: str) -> list[dict]:
        parquet = pq.ParquetFile(path)
        try:
            columns = set(parquet.schema_arrow.names)
            missing = set(REQUIRED_COLUMNS[modality]) - columns
            if missing:
                raise ExecutionFailure(
                    f"{modality} artifact lacks required columns: {sorted(missing)}"
                )
            rows = [
                row
                for batch in parquet.iter_batches(batch_size=4096)
                for row in batch.to_pylist()
            ]
        finally:
            parquet.close()
        for row in rows:
            if not row.get("case_id") or not row.get("sample_id") or not row.get("gene_id"):
                raise ExecutionFailure("canonical rows require non-null identity columns")
        return rows

    @staticmethod
    def _cohort_rows(rows: list[dict], cohort: dict) -> list[dict]:
        cases = set(cohort["case_ids"])
        samples = set(cohort["sample_ids"])
        pairs = set(cohort["member_pairs"])
        selected = []
        for row in rows:
            pair = (row["case_id"], row["sample_id"])
            if pair in pairs:
                selected.append(row)
            elif row["case_id"] in cases or row["sample_id"] in samples:
                raise ExecutionFailure(
                    "molecular row case/sample relationship conflicts with the frozen cohort"
                )
        return selected

    @staticmethod
    def _cohort(factory, store: ObjectStore, frozen: "_FrozenAnalysis"):
        with factory() as session:
            service = DurableResourceService(session)
            cohort = service.cohorts.get(frozen.cohort_id)
            if cohort is None:
                raise IntegrityFailure("cohort not found")
            snapshot = service.snapshots.get(frozen.snapshot_id)
            if snapshot is None:
                raise IntegrityFailure("snapshot not found")
            with tempfile.TemporaryDirectory(prefix="cancerjev-cohort-execute-") as tmp:
                _, graph = _guarded_artifact_operation(
                    "frozen snapshot unusable",
                    lambda: FrozenSnapshotReader(service, store, StorageSettings()).load(
                        frozen.snapshot_id, Path(tmp)
                    ),
                )
            sample_case = {sample.sample_id: sample.case_id for sample in graph.samples}
            member_pairs = tuple(
                sorted(
                    (sample_case[sample_id], sample_id)
                    for sample_id in cohort.sample_ids
                    if sample_id in sample_case and sample_case[sample_id] in cohort.case_ids
                )
            )
            if len(member_pairs) != len(cohort.sample_ids):
                raise IntegrityFailure("cohort membership drifted from the frozen snapshot")
            return {
                "cohort_id": cohort.cohort_id,
                "content_hash": cohort.content_hash,
                "case_ids": tuple(cohort.case_ids),
                "sample_ids": tuple(cohort.sample_ids),
                "member_pairs": member_pairs,
                "snapshot_hash": snapshot.snapshot_hash,
            }

    @classmethod
    def _completed_result(cls, session: Session, analysis) -> dict:
        findings = DurableResourceService(session).findings.list(
            snapshot_id=None,
            cohort_id=None,
            analysis_id=str(analysis.analysis_id),
            finding_type=None,
            gene=None,
            result_hash=None,
            limit=1000,
            offset=0,
        )
        return {
            "analysis_id": str(analysis.analysis_id),
            "published": len(findings),
            "finding_ids": [row.finding_id for row in findings],
            "converged": True,
        }

    @classmethod
    def _converged_result(cls, factory, analysis_id: str) -> dict:
        with factory() as session:
            analysis = DurableResourceService(session).analyses.get(analysis_id)
            if analysis is not None and analysis.state == "completed":
                return cls._completed_result(session, analysis)
        raise LeaseLostError("job lease was lost before publication")


class _FrozenAnalysis:
    """Immutable view of the analysis row captured after the running transition."""

    def __init__(self, row):
        self.analysis_id = str(row.analysis_id)
        self.snapshot_id = row.snapshot_id
        self.cohort_id = row.cohort_id
        self.engine = row.engine
        self.engine_version = row.engine_version
        self.parameters = dict(row.parameters)
        self.expected_input_artifacts = list(row.expected_input_artifacts)
        self.input_materializations = list(row.input_materializations)

    @classmethod
    def from_row(cls, row) -> "_FrozenAnalysis":
        return cls(row)

    def engine_context(self, cohort: dict, spec: EngineSpec) -> EngineContext:
        return EngineContext(
            snapshot_id=self.snapshot_id,
            snapshot_hash=cohort["snapshot_hash"],
            cohort_id=cohort["cohort_id"],
            cohort_content_hash=cohort["content_hash"],
            cohort_size=len(cohort["case_ids"]),
            engine_version=self.engine_version,
            method_version=spec.method_version,
            parameters=self.parameters,
            input_hashes=tuple(sorted(self.expected_input_artifacts)),
            environment=runtime_environment(),
        )
