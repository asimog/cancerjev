from pathlib import Path
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from packages.storage.objects import (
    ObjectStorePermissionError,
    ObjectStoreServiceError,
    S3ObjectStore,
)


def store_with_client(client: Mock) -> S3ObjectStore:
    store = object.__new__(S3ObjectStore)
    store.bucket = "test"
    store.client = client
    return store


def client_error(code: str, status: int) -> ClientError:
    return ClientError(
        {"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}},
        "HeadObject",
    )


def test_s3_not_found_is_false() -> None:
    client = Mock()
    client.head_object.side_effect = client_error("NoSuchKey", 404)
    assert not store_with_client(client).exists("a" * 64)


def test_s3_permission_failure_is_not_missing() -> None:
    client = Mock()
    client.head_object.side_effect = client_error("AccessDenied", 403)
    with pytest.raises(ObjectStorePermissionError):
        store_with_client(client).exists("a" * 64)


def test_s3_service_failure_is_not_missing() -> None:
    client = Mock()
    client.head_object.side_effect = EndpointConnectionError(endpoint_url="http://minio")
    with pytest.raises(ObjectStoreServiceError):
        store_with_client(client).exists("a" * 64)


def test_s3_bounded_stage_verifies_bytes(tmp_path):
    import hashlib
    from unittest.mock import Mock

    from packages.storage.objects import S3ObjectStore, object_key

    store = object.__new__(S3ObjectStore)
    store.bucket = "test"
    store.client = Mock()
    source = b"payload"
    digest = "sha256:" + hashlib.sha256(source).hexdigest()
    target = tmp_path / "source"
    store.client.download_file.side_effect = lambda bucket, key, path: Path(path).write_bytes(
        source
    )
    store.stage(digest, target)
    store.client.download_file.assert_called_once_with("test", object_key(digest), str(target))
    store.client.get_object.assert_not_called()
    store.client.download_file.side_effect = lambda bucket, key, path: Path(path).write_bytes(
        b"bad"
    )
    with pytest.raises(ValueError, match="SHA-256"):
        store.stage(digest, target)
    assert not target.exists()


@pytest.mark.parametrize("method", ["put", "put_file"])
def test_file_cas_concurrent_publication_preserves_winner(tmp_path, monkeypatch, method):
    import hashlib
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from packages.storage.objects import FileObjectStore, object_key

    source = tmp_path / "source"
    source.write_bytes(b"shared immutable bytes")
    digest = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
    store = FileObjectStore(tmp_path / "objects")
    target = store.root / object_key(digest)
    barrier = threading.Barrier(2)
    original_exists = Path.exists

    def race_exists(path):
        if path == target:
            barrier.wait(timeout=10)
            return False  # Both writers observed the key before publication.
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", race_exists)
    value = source.read_bytes() if method == "put" else source
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: getattr(store, method)(value), range(2)))
    assert results == [digest, digest]
    assert target.read_bytes() == source.read_bytes()
    assert list(target.parent.iterdir()) == [target]


@pytest.mark.parametrize("method", ["put", "put_file"])
def test_file_cas_rejects_existing_corrupt_object(tmp_path, method):
    from packages.storage.objects import FileObjectStore, object_key

    store = FileObjectStore(tmp_path / "objects")
    source = tmp_path / "source"
    source.write_bytes(b"correct")
    digest = store.put(source.read_bytes())
    (store.root / object_key(digest)).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="existing CAS object"):
        getattr(store, method)(source.read_bytes() if method == "put" else source)
