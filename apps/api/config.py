from pathlib import Path

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CANCERJEV_", env_file=".env", extra="ignore")

    gdc_base_url: AnyHttpUrl = "https://api.gdc.cancer.gov"
    gdc_timeout_seconds: float = Field(default=30, gt=0)
    gdc_max_connections: int = Field(default=8, ge=1, le=8)
    gdc_max_response_bytes: int = Field(default=100_000_000, ge=1)
    database_url: str = Field(default="postgresql+psycopg://localhost/cancerjev")
    snapshot_root: Path = Path(".data/snapshots")

    @property
    def storage_settings(self):
        from packages.storage.config import StorageSettings
        return StorageSettings()


settings = Settings()
