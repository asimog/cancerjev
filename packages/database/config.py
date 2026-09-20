import os


def resolve_database_url(configured_url: str | None = None) -> str:
    """Resolve the single runtime DB setting without logging credentials."""
    value = os.getenv("CANCERJEV_DATABASE_URL") or configured_url
    if not value:
        raise RuntimeError("CANCERJEV_DATABASE_URL is required")
    return value
