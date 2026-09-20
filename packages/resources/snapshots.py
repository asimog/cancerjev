"""Verified reader for the frozen snapshot graph shared by resource operations."""

import shutil
from pathlib import Path

import pyarrow.parquet as pq

from packages.gdc.identity import FrozenIdentityResolver
from packages.gdc.policy import official_api, require_open
from packages.provenance.hashing import sha256_file
from packages.schemas.identity import AliquotRecord, CaseRecord, FileSampleLink, SampleRecord
from packages.schemas.snapshot import SnapshotRecord
from packages.storage.config import StorageSettings
from packages.storage.objects import ObjectStore, object_key


class FrozenSnapshotReader:
    def __init__(self, resources, store: ObjectStore, settings: StorageSettings):
        self.resources, self.store, self.settings = resources, store, settings

    def stage(self, artifact, destination: Path) -> None:
        if artifact.storage_key == object_key(artifact.sha256):
            if artifact.storage_backend != self.settings.object_backend:
                raise ValueError("artifact backend differs from configured object store")
            self.store.stage(artifact.sha256, destination)
        else:
            # PR #7 snapshots register immutable snapshot-relative paths, not CAS keys.
            if artifact.storage_backend != "filesystem":
                raise ValueError("unsupported legacy artifact backend")
            root = self.settings.snapshot_root.resolve()
            source = (root / artifact.storage_key).resolve()
            if root not in source.parents:
                raise ValueError("snapshot artifact escapes configured root")
            shutil.copyfile(source, destination)
            if sha256_file(str(destination)) != artifact.sha256:
                raise ValueError("snapshot artifact hash mismatch")
        if destination.stat().st_size != artifact.size:
            raise ValueError("artifact size mismatch")

    def load(self, snapshot_id: str, directory: Path):
        artifacts = self.resources.snapshot_artifacts(snapshot_id)
        required = {"snapshot", "cases", "samples", "aliquots", "identity_links"}
        if not required.issubset(artifacts):
            raise ValueError("snapshot lacks frozen identity artifacts")
        for role in sorted(required):
            self.stage(artifacts[role], directory / role)
        snapshot = SnapshotRecord.model_validate_json((directory / "snapshot").read_bytes())
        durable = self.resources.snapshots.get(snapshot_id)
        if snapshot.snapshot_id != snapshot_id or snapshot.snapshot_hash != durable.snapshot_hash:
            raise ValueError("snapshot context mismatch")
        official_api(snapshot.source_api)
        for item in snapshot.objects:
            require_open(item.access)
        if durable.status != "published":
            raise ValueError("snapshot is not frozen/published")
        models = (
            ("cases", CaseRecord),
            ("samples", SampleRecord),
            ("aliquots", AliquotRecord),
            ("identity_links", FileSampleLink),
        )
        # Identity memory scales with frozen cohort metadata, never molecular row count.
        values = [
            tuple(
                model.model_validate(row)
                for batch in pq.ParquetFile(directory / role).iter_batches(batch_size=4096)
                for row in batch.to_pylist()
            )
            for role, model in models
        ]
        graph = FrozenIdentityResolver(*values)
        if (
            set(snapshot.case_ids) != graph.case_ids
            or set(snapshot.sample_ids) != {s.sample_id for s in graph.samples}
            or set(snapshot.aliquot_ids) != {a.aliquot_id for a in graph.aliquots}
            or not {link.file_id for link in graph.links}.issubset(
                {item.file_id for item in snapshot.objects}
            )
        ):
            raise ValueError("snapshot identity graph does not match frozen membership")
        return snapshot, graph
