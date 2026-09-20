"""Application orchestration: frozen resources -> scientific bytes -> durable lineage."""

import json
import shutil
import tempfile
from pathlib import Path

from packages.gdc.identity import SELECTION_VERSION
from packages.gdc.materialization import materialize_verified
from packages.gdc.normalization import NORMALIZATION_VERSION
from packages.gdc.parsers import MAX_CLINICAL_BYTES, select_parser
from packages.gdc.policy import GDC_API
from packages.gdc.transfer import verify_file
from packages.provenance.hashing import canonical_hash
from packages.resources.service import DurableResourceService, ResourceConflictError
from packages.resources.snapshots import FrozenSnapshotReader
from packages.schemas.materialization import MaterializationRequest
from packages.schemas.resources import ArtifactRegistration
from packages.schemas.snapshot import SnapshotObject
from packages.storage.config import StorageSettings
from packages.storage.objects import ObjectStore, object_key


class MaterializationService:
    def __init__(
        self, resources: DurableResourceService, store: ObjectStore, settings: StorageSettings
    ):
        self.resources, self.store, self.settings = resources, store, settings
        self.reader = FrozenSnapshotReader(resources, store, settings)

    async def acquire_clinical_sources(self, snapshot_id: str, client):
        """Freeze each bounded official cases page in the same durable source contract."""
        with tempfile.TemporaryDirectory(prefix="cancerjev-clinical-") as tmp:
            root = Path(tmp)
            snapshot, _ = self.reader.load(snapshot_id, root)
            async for raw, provenance in client.clinical_pages(snapshot.case_ids):
                page = root / "clinical.json"
                page.write_bytes(raw)
                yield self.register_local_source(
                    snapshot_id,
                    page,
                    clinical_provenance=provenance,
                )

    def _artifact(self, path: Path, role: str, **kwargs) -> ArtifactRegistration:
        digest = self.store.put_file(path)
        return ArtifactRegistration(
            sha256=digest,
            size=path.stat().st_size,
            media_type="application/vnd.apache.parquet"
            if path.suffix == ".parquet"
            else "application/octet-stream",
            logical_role=role,
            storage_backend=self.settings.object_backend,
            storage_key=object_key(digest),
            **kwargs,
        )

    def register_local_source(
        self,
        snapshot_id: str,
        path: Path,
        *,
        file_id: str | None = None,
        clinical_provenance: dict | None = None,
    ):
        """Trusted acquisition boundary for already acquired payloads, never a job path input."""
        with tempfile.TemporaryDirectory(prefix="cancerjev-register-") as tmp:
            root = Path(tmp)
            snapshot, _ = self.reader.load(snapshot_id, root)
            staged = root / "source"
            shutil.copyfile(path, staged)
            if file_id:
                matches = [f for f in snapshot.objects if f.file_id == file_id]
                if len(matches) != 1 or matches[0].access != "open":
                    raise ValueError("source file not in frozen open snapshot")
                source = matches[0]
                # Name association is checked at acquisition; storage keys are hashes thereafter.
                if path.name != source.file_name:
                    raise ValueError("source filename association mismatch")
                verify_file(staged, source.md5sum, source.file_size)
                metadata = {"kind": "gdc_file", "file": source.model_dump(mode="json")}
            else:
                if not clinical_provenance or (
                    clinical_provenance.get("endpoint") != GDC_API + "/cases"
                    or not clinical_provenance.get("acquired_at")
                    or not isinstance(clinical_provenance.get("query"), dict)
                ):
                    raise ValueError("clinical API acquisition provenance is required")
                if staged.stat().st_size > MAX_CLINICAL_BYTES:
                    raise ValueError("clinical_page_exceeds_limit")
                payload = json.loads(staged.read_bytes())
                hits = payload.get("data", {}).get("hits")
                if not isinstance(hits, list) or any(
                    not isinstance(c, dict) or c.get("case_id") not in snapshot.case_ids
                    for c in hits
                ):
                    raise ValueError("clinical page contains non-frozen case identity")
                metadata = {"kind": "gdc_clinical_api", "provenance": clinical_provenance}
            artifact = self._artifact(
                staged,
                "gdc_source",
                source_gdc_uuid=file_id,
                source_md5=source.md5sum if file_id else None,
            )
            return self.resources.register_source(
                snapshot_id=snapshot_id,
                artifact=artifact,
                source_file_id=file_id,
                source_metadata=metadata,
            )

    def run(self, request: MaterializationRequest, *, batch_size: int = 4096) -> dict:
        binding = self.resources.get_source(request.source_id)
        if (
            binding.snapshot_id != request.snapshot_id
            or binding.sha256 != request.expected_source_sha256
        ):
            raise ResourceConflictError("source/snapshot/hash mismatch")
        with tempfile.TemporaryDirectory(prefix="cancerjev-materialize-") as tmp:
            root = Path(tmp)
            snapshot, identity = self.reader.load(request.snapshot_id, root)
            source = None
            if binding.source_file_id:
                matches = [f for f in snapshot.objects if f.file_id == binding.source_file_id]
                if len(matches) != 1:
                    raise ValueError("source missing from frozen snapshot")
                source = matches[0]
                if source != SnapshotObject.model_validate(binding.source_metadata["file"]):
                    raise ValueError("source frozen metadata mismatch")
            elif binding.source_metadata.get("kind") != "gdc_clinical_api":
                raise ValueError("unsupported source binding")
            parser = select_parser(
                modality=request.modality,
                version=request.parser_version,
                source=source,
                measurement=request.measurement_type,
            )
            lineage = {
                "snapshot_id": request.snapshot_id,
                "source_id": request.source_id,
                "modality": request.modality,
                "measurement_type": request.measurement_type,
                "parser_name": parser.name,
                "parser_version": parser.version,
                "schema_version": parser.schema_version,
                "normalization_version": NORMALIZATION_VERSION,
                "selection_version": SELECTION_VERSION,
            }
            materialization_id = canonical_hash(lineage)
            # Check source bytes and frozen context on retry without reparsing existing output.
            source_artifact = self.resources.artifacts.get(binding.sha256)
            self.reader.stage(source_artifact, root / "source")
            if source:
                verify_file(root / "source", source.md5sum, source.file_size)
            existing = self.resources.get_materialization(materialization_id)
            if existing:
                return self._result(existing)
            result = materialize_verified(
                root / "source",
                root / "output",
                source=source,
                expected_file_id=binding.source_file_id,
                expected_sha256=binding.sha256,
                identity=identity,
                modality=request.modality,
                parser_version=request.parser_version,
                measurement=request.measurement_type,
                batch_size=batch_size,
            )
            output = self._artifact(
                result.parquet,
                "canonical_" + request.modality,
                parser_schema_version=result.schema_version,
                row_count=result.summary["rows_accepted"],
            )
            diagnostics = self._artifact(result.diagnostics, "materialization_diagnostics")
            value = self.resources.register_materialization(
                metadata=lineage
                | {
                    "materialization_id": materialization_id,
                    "output_sha256": output.sha256,
                    "diagnostics_sha256": diagnostics.sha256,
                    "logical_sha256": result.logical_sha256,
                    "row_count": result.summary["rows_accepted"],
                    "diagnostics_summary": result.summary,
                },
                output=output,
                diagnostics=diagnostics,
            )
            return self._result(value)

    @staticmethod
    def _result(value) -> dict:
        return {
            name: getattr(value, name)
            for name in (
                "materialization_id",
                "snapshot_id",
                "source_id",
                "modality",
                "measurement_type",
                "output_sha256",
                "diagnostics_sha256",
                "logical_sha256",
                "row_count",
            )
        }
