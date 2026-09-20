import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from packages.schemas.snapshot import SnapshotRecord

REQUIRED_ARTIFACTS = frozenset(
    {
        "snapshot.json",
        "manifest.tsv",
        "cases.parquet",
        "samples.parquet",
        "aliquots.parquet",
        "files.parquet",
        "file_sample_links.parquet",
        "coverage.parquet",
        "provenance.json",
        "COMPLETE.json",
    }
)


class SnapshotConflictError(RuntimeError):
    pass


class FileSnapshotRepository:
    """Publish complete immutable snapshot directories with an atomic rename."""

    def __init__(self, root: Path):
        self.root = root

    def publish(
        self, snapshot: SnapshotRecord, write_artifacts: Callable[[Path], None]
    ) -> SnapshotRecord:
        project_root = self.root / snapshot.project_id
        destination = project_root / snapshot.snapshot_id
        if destination.exists():
            return self._verify_existing(destination, snapshot)
        project_root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{snapshot.snapshot_id}-", dir=project_root))
        try:
            (staging / "snapshot.json").write_text(
                snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
            write_artifacts(staging)
            missing = set(REQUIRED_ARTIFACTS - {item.name for item in staging.iterdir()})
            missing.discard("COMPLETE.json")
            if missing:
                raise RuntimeError(f"snapshot build missing artifacts: {sorted(missing)}")
            (staging / "COMPLETE.json").write_text(
                json.dumps(
                    {
                        "artifact_hashes": {
                            path.name: self._digest(path)
                            for path in sorted(staging.iterdir(), key=lambda item: item.name)
                            if path.is_file()
                        },
                        "snapshot_hash": snapshot.snapshot_hash,
                        "publication_version": "1",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            self._sync_tree(staging)
            try:
                staging.replace(destination)
            except OSError:
                if destination.exists():
                    return self._verify_existing(destination, snapshot)
                raise
            return snapshot
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    def _verify_existing(self, destination: Path, expected: SnapshotRecord) -> SnapshotRecord:
        missing = REQUIRED_ARTIFACTS - {item.name for item in destination.iterdir()}
        if missing:
            raise SnapshotConflictError(f"existing snapshot is incomplete: {sorted(missing)}")
        try:
            stored = SnapshotRecord.model_validate_json(
                (destination / "snapshot.json").read_text(encoding="utf-8")
            )
            marker = json.loads((destination / "COMPLETE.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SnapshotConflictError("existing snapshot metadata is corrupt") from exc
        if (
            stored.snapshot_hash != expected.snapshot_hash
            or marker.get("snapshot_hash") != expected.snapshot_hash
        ):
            raise SnapshotConflictError("existing snapshot identity conflicts with requested input")
        artifact_hashes = marker.get("artifact_hashes")
        if not isinstance(artifact_hashes, dict) or any(
            self._digest(destination / name) != digest for name, digest in artifact_hashes.items()
        ):
            raise SnapshotConflictError("existing snapshot artifact hashes do not verify")
        return stored

    @staticmethod
    def _digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return f"sha256:{digest.hexdigest()}"

    @staticmethod
    def _sync_tree(root: Path) -> None:
        for path in root.iterdir():
            if path.is_file():
                with path.open("r+b") as stream:
                    os.fsync(stream.fileno())
