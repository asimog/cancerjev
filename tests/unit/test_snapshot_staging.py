"""Reference-owned artifact staging: identical bytes, distinct registered locations."""

from pathlib import Path

from packages.database.models import ArtifactReference
from packages.resources.snapshots import FrozenSnapshotReader
from packages.storage.config import StorageSettings
from packages.storage.objects import FileObjectStore, object_key


def reference(role: str, backend: str, key: str, digest: str, size: int) -> ArtifactReference:
    return ArtifactReference(
        sha256=digest,
        size=size,
        media_type="application/octet-stream",
        logical_role=role,
        storage_backend=backend,
        storage_key=key,
    )


def test_reference_locator_selects_its_own_storage_location(tmp_path: Path) -> None:
    settings = StorageSettings(
        object_root=tmp_path / "objects", snapshot_root=tmp_path / "snapshots"
    )
    store = FileObjectStore(settings.object_root)
    payload = b"same bytes, two registered locations"
    digest = store.put(payload)
    legacy = settings.snapshot_root / "TCGA-LUAD" / "DS-1" / "manifest.tsv"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(payload)

    reader = FrozenSnapshotReader(resources=None, store=store, settings=settings)
    cases = reference("cases", "filesystem", object_key(digest), digest, len(payload))
    manifest = reference(
        "manifest", "filesystem", "TCGA-LUAD/DS-1/manifest.tsv", digest, len(payload)
    )

    cases_destination = tmp_path / "staged-cases"
    reader.stage(cases, cases_destination)
    assert cases_destination.read_bytes() == payload

    # With the CAS copy gone, only the reference's own locator can resolve the bytes.
    (settings.object_root / object_key(digest)).unlink()
    manifest_destination = tmp_path / "staged-manifest"
    reader.stage(manifest, manifest_destination)
    assert manifest_destination.read_bytes() == payload


def test_reference_locator_cannot_escape_the_snapshot_root(tmp_path: Path) -> None:
    settings = StorageSettings(
        object_root=tmp_path / "objects", snapshot_root=tmp_path / "snapshots"
    )
    store = FileObjectStore(settings.object_root)
    payload = b"escaped bytes"
    digest = store.put(payload)
    outside = tmp_path / "outside" / "manifest.tsv"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_bytes(payload)

    reader = FrozenSnapshotReader(resources=None, store=store, settings=settings)
    artifact = reference("manifest", "filesystem", "../outside/manifest.tsv", digest, len(payload))
    try:
        reader.stage(artifact, tmp_path / "staged-escape")
    except ValueError as exc:
        assert "escapes" in str(exc)
    else:
        raise AssertionError("snapshot artifact escaped the configured root")