"""Resolve analysis inputs from immutable materializations — never from caller payloads.

Given an Analysis, resolves Snapshot → Cohort → required Materializations →
DatasetObjects → verified Parquet files. Rejects wrong snapshot, wrong cohort,
cross-snapshot references, wrong modality/measurement, corrupt objects.
"""

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from packages.database.models import Materialization
from packages.gdc.identity import FrozenIdentityResolver
from packages.provenance.hashing import sha256_file
from packages.resources.service import DurableResourceService
from packages.schemas.identity import AliquotRecord, CaseRecord, FileSampleLink, SampleRecord
from packages.schemas.snapshot import SnapshotRecord
from packages.statistics.registry import resolve_engine
from packages.storage.config import StorageSettings
from packages.storage.objects import ObjectStore


class InputResolutionError(ValueError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class ResolvedInput:
    materialization: Materialization
    local_path: Path
    parsed: list[dict]


@dataclass(frozen=True)
class AnalysisInputManifest:
    analysis_id: str
    snapshot_id: str
    cohort_id: str
    engine: str
    engine_version: str
    parameters: dict
    purpose: str  # EXPLORATORY, CONFIRMATORY, REPLICATION
    eligibility_snapshot_hash: str
    cohort_case_ids: tuple[str, ...]
    cohort_sample_ids: tuple[str, ...]
    materializations: dict[str, list[ResolvedInput]]
    population: dict
    identity: FrozenIdentityResolver


class AnalysisInputResolver:
    """Resolve a durable Analysis into verified local Parquet files and identity."""

    def __init__(
        self,
        session: Session,
        resources: DurableResourceService,
        store: ObjectStore,
        settings: StorageSettings,
    ):
        self.session = session
        self.resources = resources
        self.store = store
        self.settings = settings

    def resolve(self, analysis_id: str, purpose: str = "EXPLORATORY") -> AnalysisInputManifest:
        analysis = self.resources.analyses.get(analysis_id)
        if analysis is None:
            raise InputResolutionError(f"analysis not found: {analysis_id}")

        if analysis.state not in ("queued", "running"):
            raise InputResolutionError(f"analysis {analysis_id} is in state {analysis.state}")

        engine, params = resolve_engine(analysis.engine, analysis.engine_version, analysis.parameters)

        snapshot = self.resources.snapshots.get(analysis.snapshot_id)
        if snapshot is None:
            raise InputResolutionError(f"snapshot not found: {analysis.snapshot_id}")

        cohort = self.resources.cohorts.get(str(analysis.cohort_id))
        if cohort is None or cohort.snapshot_id != snapshot.snapshot_id:
            raise InputResolutionError(f"cohort {analysis.cohort_id} does not belong to snapshot {analysis.snapshot_id}")

        snapshot_artifact = self.resources.snapshots.get(snapshot.snapshot_id)
        if snapshot_artifact is None:
            raise InputResolutionError("snapshot artifact registry missing")

        with tempfile.TemporaryDirectory(prefix="analysis-resolver-") as tmp:
            root = Path(tmp)
            artifacts = self.resources.snapshot_artifacts(snapshot.snapshot_id)
            required = {"snapshot", "cases", "samples", "aliquots", "identity_links"}
            if not required.issubset(artifacts):
                raise InputResolutionError("snapshot lacks frozen identity artifacts")
            for role in sorted(required):
                artifact = artifacts[role]
                if artifact.storage_backend == "filesystem":
                    src = self.settings.snapshot_root.resolve() / artifact.storage_key
                    if not src.exists():
                        raise InputResolutionError(f"missing identity artifact: {role}")
                    shutil.copyfile(src, root / role)
                else:
                    self.store.stage(artifact.sha256, root / role)

            parsed_snapshot = SnapshotRecord.model_validate_json((root / "snapshot").read_bytes())
            if parsed_snapshot.snapshot_hash != snapshot.snapshot_hash:
                raise InputResolutionError("snapshot identity mismatch")

            identity = self._load_identity(root)

            materializations = {}
            for modality in engine.modalities:
                existing = self.resources.list_materializations(
                    snapshot.snapshot_id, modality,
                    params.measurement_type if hasattr(params, "measurement_type") else "",
                )
                if not existing:
                    raise InputResolutionError(f"no materialization for modality {modality}")
                materializations[modality] = []
                for mat in existing:
                    local = root / f"{modality}_{mat.materialization_id}.parquet"
                    artifact = self.resources.artifacts.get(mat.output_sha256)
                    if artifact is None:
                        raise InputResolutionError(f"output artifact missing: {mat.output_sha256}")
                    if artifact.storage_backend == "filesystem":
                        src = self.settings.snapshot_root.resolve() / artifact.storage_key
                        shutil.copyfile(src, local)
                    else:
                        self.store.stage(artifact.sha256, local)
                    if sha256_file(str(local)) != mat.output_sha256:
                        raise InputResolutionError(f"corrupt materialization output: {mat.materialization_id}")

                    import pyarrow.parquet as pq
                    rows = [row for batch in pq.ParquetFile(local).iter_batches(batch_size=4096) for row in batch.to_pylist()]
                    materializations[modality].append(ResolvedInput(mat, local, rows))

        excluded_ids = set()
        if purpose == "EXPLORATORY":
            for sid in cohort.sample_ids:
                if sid not in identity.sample_id_set:
                    excluded_ids.add(sid)

        return AnalysisInputManifest(
            analysis_id=str(analysis.analysis_id),
            snapshot_id=analysis.snapshot_id,
            cohort_id=str(analysis.cohort_id),
            engine=analysis.engine,
            engine_version=analysis.engine_version,
            parameters=params.model_dump(mode="json"),
            purpose=purpose,
            eligibility_snapshot_hash=snapshot.snapshot_hash,
            cohort_case_ids=tuple(cohort.case_ids),
            cohort_sample_ids=tuple(cohort.sample_ids),
            materializations=materializations,
            population={
                "total_cases": len(cohort.case_ids),
                "total_samples": len(cohort.sample_ids),
                "excluded": list(excluded_ids),
                "eligible_cases": len(cohort.case_ids),
                "eligible_samples": len(cohort.sample_ids) - len(excluded_ids),
            },
            identity=identity,
        )

    def _load_identity(self, root: Path) -> FrozenIdentityResolver:
        from packages.storage.parquet import read_records
        cases = tuple(read_records(root / "cases", CaseRecord))
        samples = tuple(read_records(root / "samples", SampleRecord))
        aliquots = tuple(read_records(root / "aliquots", AliquotRecord))
        links = tuple(read_records(root / "file_sample_links", FileSampleLink))
        return FrozenIdentityResolver(cases, samples, aliquots, links)