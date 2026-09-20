import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError


class ObjectStoreError(RuntimeError):
    pass


class ObjectStorePermissionError(ObjectStoreError):
    pass


class ObjectStoreServiceError(ObjectStoreError):
    pass


class ObjectStore(Protocol):
    def put(self, data: bytes, expected_sha256: str | None = None) -> str: ...
    def put_file(self, path: Path, expected_sha256: str | None = None) -> str: ...
    def get(self, digest: str) -> bytes: ...
    def stage(self, digest: str, destination: Path) -> None: ...
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

    def put_file(self, source: Path, expected_sha256: str | None = None) -> str:
        digest = _hash_file(source)
        if expected_sha256 and expected_sha256 != digest:
            raise ValueError("SHA-256 mismatch")
        destination = self._path(digest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
                temporary = Path(stream.name)
            try:
                shutil.copyfile(source, temporary)
                if _hash_file(temporary) != digest:
                    raise ValueError("source changed during object publication")
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
        return digest

    def stage(self, digest: str, destination: Path) -> None:
        shutil.copyfile(self._path(digest), destination)
        if _hash_file(destination) != digest:
            destination.unlink()
            raise ValueError("object SHA-256 mismatch")

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

    def put_file(self, path: Path, expected_sha256: str | None = None) -> str:
        digest = _hash_file(path)
        if expected_sha256 and digest != expected_sha256:
            raise ValueError("SHA-256 mismatch")
        if not self.exists(digest):
            self.client.upload_file(str(path), self.bucket, object_key(digest))
        return digest

    def get(self, digest: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=object_key(digest))["Body"].read()

    def stage(self, digest: str, destination: Path) -> None:
        self.client.download_file(self.bucket, object_key(digest), str(destination))
        if _hash_file(destination) != digest:
            destination.unlink()
            raise ValueError("object SHA-256 mismatch")

    def exists(self, digest: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=object_key(digest))
            return True
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = str(error.get("Code", ""))
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in {"404", "NoSuchKey", "NotFound"} or status == 404:
                return False
            permission_codes = {
                "401",
                "403",
                "AccessDenied",
                "InvalidAccessKeyId",
                "SignatureDoesNotMatch",
            }
            if code in permission_codes or status in {401, 403}:
                raise ObjectStorePermissionError("object-store access denied") from exc
            if isinstance(status, int) and status >= 500:
                raise ObjectStoreServiceError("object-store service unavailable") from exc
            raise ObjectStoreError("object-store lookup failed") from exc
        except BotoCoreError as exc:
            raise ObjectStoreServiceError("object-store transport failed") from exc

    def verify(self, digest: str) -> bool:
        return (
            self.exists(digest)
            and f"sha256:{hashlib.sha256(self.get(digest)).hexdigest()}" == digest
        )

    def delete_cache_object(self, key: str) -> None:
        if ".." in Path(key).parts:
            raise ValueError("invalid cache key")
        self.client.delete_object(Bucket=self.bucket, Key=f"cache/{key}")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
