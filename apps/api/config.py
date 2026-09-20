from pathlib import Path

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CANCERJEV_", env_file=".env")

    gdc_base_url: AnyHttpUrl = "https://api.gdc.cancer.gov"
    gdc_timeout_seconds: float = Field(default=30, gt=0)
    gdc_max_connections: int = Field(default=8, ge=1, le=8)
    snapshot_root: Path = Path(".data/snapshots")


settings = Settings()
