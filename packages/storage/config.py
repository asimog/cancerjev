"""Shared object-store runtime configuration for source registration and workers."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.storage.objects import FileObjectStore, ObjectStore, S3ObjectStore


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CANCERJEV_", env_file=".env", extra="ignore")
    object_backend: Literal["filesystem", "s3"] = "filesystem"
    object_root: Path = Path(".data/objects")
    snapshot_root: Path = Path(".data/snapshots")
    object_bucket: str | None = None
    object_endpoint_url: str | None = None

    def store(self) -> ObjectStore:
        if self.object_backend == "filesystem":
            return FileObjectStore(self.object_root)
        if not self.object_bucket:
            raise ValueError("CANCERJEV_OBJECT_BUCKET is required for S3")
        options = {"endpoint_url": self.object_endpoint_url} if self.object_endpoint_url else {}
        return S3ObjectStore(self.object_bucket, **options)
