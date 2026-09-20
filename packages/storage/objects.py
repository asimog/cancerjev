import hashlib
from pathlib import Path
from typing import Protocol

import boto3


class ObjectStore(Protocol):
    def put(self, data: bytes, expected_sha256: str | None = None) -> str: ...
    def get(self, digest: str) -> bytes: ...
    def exists(self, digest: str) -> bool: ...
    def verify(self, digest: str) -> bool: ...
    def delete_cache_object(self, key: str) -> None: ...


def object_key(digest: str) -> str:
    value = digest.removeprefix("sha256:").lower()
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("invalid SHA-256 digest")
    return f"sha256/{value[:2]}/{value[2:4]}/{value}"


class FileObjectStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, digest: str) -> Path:
        return self.root / object_key(digest)

    def put(self, data: bytes, expected_sha256: str | None = None) -> str:
        digest = f"sha256:{hashlib.sha256(data).hexdigest()}"
        if expected_sha256 and expected_sha256 != digest:
            raise ValueError("SHA-256 mismatch")
        path = self._path(digest)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
        return digest

    def get(self, digest: str) -> bytes:
        return self._path(digest).read_bytes()

    def exists(self, digest: str) -> bool:
        return self._path(digest).is_file()

    def verify(self, digest: str) -> bool:
        return (
            self.exists(digest)
            and f"sha256:{hashlib.sha256(self.get(digest)).hexdigest()}" == digest
        )

    def delete_cache_object(self, key: str) -> None:
        if ".." in Path(key).parts:
            raise ValueError("invalid cache key")
        path = self.root / "cache" / key
        if path.is_file():
            path.unlink()


class S3ObjectStore:
    def __init__(self, bucket: str, **client_options: object):
        self.bucket = bucket
        self.client = boto3.client("s3", **client_options)

    def put(self, data: bytes, expected_sha256: str | None = None) -> str:
        digest = f"sha256:{hashlib.sha256(data).hexdigest()}"
        if expected_sha256 and digest != expected_sha256:
            raise ValueError("SHA-256 mismatch")
        if not self.exists(digest):
            self.client.put_object(Bucket=self.bucket, Key=object_key(digest), Body=data)
        return digest

    def get(self, digest: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=object_key(digest))["Body"].read()

    def exists(self, digest: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=object_key(digest))
            return True
        except self.client.exceptions.ClientError:
            return False

    def verify(self, digest: str) -> bool:
        return (
            self.exists(digest)
            and f"sha256:{hashlib.sha256(self.get(digest)).hexdigest()}" == digest
        )

    def delete_cache_object(self, key: str) -> None:
        if ".." in Path(key).parts:
            raise ValueError("invalid cache key")
        self.client.delete_object(Bucket=self.bucket, Key=f"cache/{key}")
