from pathlib import Path

from packages.schemas.snapshot import SnapshotRecord


class FileSnapshotRepository:
    """Atomic filesystem implementation of the snapshot persistence boundary."""

    def __init__(self, root: Path):
        self.root = root

    def save(self, snapshot: SnapshotRecord) -> Path:
        destination = self.root / snapshot.project_id / snapshot.snapshot_id / "snapshot.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(destination)
        return destination
