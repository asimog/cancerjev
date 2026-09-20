from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CANCERJEV_", env_file=".env")

    gdc_base_url: AnyHttpUrl = "https://api.gdc.cancer.gov"
    gdc_timeout_seconds: float = Field(default=30, gt=0)
    gdc_max_connections: int = Field(default=8, ge=1, le=8)
    snapshot_root: Path = Path(".data/snapshots")

    # Generative research and Jev are deliberately separate provider boundaries.
    # In particular, never silently send a Jev evaluation to the LLM endpoint.
    llm_base_url: AnyHttpUrl = "https://openrouter.ai/api/v1"
    llm_api_key: SecretStr | None = None
    llm_model: str = "openai/gpt-5-mini"
    jev_base_url: AnyHttpUrl = "https://api.typesafe.ai"
    jev_api_key: SecretStr | None = None
    jev_model: str = "jev-latest"
    ai_timeout_seconds: float = Field(default=30, gt=0)


settings = Settings()
