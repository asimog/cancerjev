from pathlib import Path

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.gdc.policy import GDC_API, official_api


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CANCERJEV_", env_file=".env", extra="ignore")

    gdc_base_url: AnyHttpUrl = GDC_API
    gdc_timeout_seconds: float = Field(default=30, gt=0)
    gdc_max_connections: int = Field(default=8, ge=1, le=8)
    gdc_max_response_bytes: int = Field(default=100_000_000, ge=1)
    database_url: str = Field(default="postgresql+psycopg://localhost/cancerjev")
    snapshot_root: Path = Path(".data/snapshots")

    @field_validator("gdc_base_url")
    @classmethod
    def official_gdc_host(cls, value):
        official_api(str(value))
        return value


settings = Settings()
