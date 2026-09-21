from alembic.config import Config

from apps.api.config import Settings
from packages.database.config import resolve_database_url


def test_runtime_and_migrations_resolve_same_authoritative_url(monkeypatch) -> None:
    expected = "postgresql+psycopg://user:secret@example.invalid/cancerjev"
    monkeypatch.setenv("CANCERJEV_DATABASE_URL", expected)
    alembic = Config("alembic.ini")
    assert resolve_database_url() == expected
    assert resolve_database_url(alembic.get_main_option("sqlalchemy.url")) == expected


def test_database_url_is_required_without_runtime_or_tooling_value(monkeypatch) -> None:
    monkeypatch.delenv("CANCERJEV_DATABASE_URL", raising=False)
    try:
        resolve_database_url()
    except RuntimeError as exc:
        assert "required" in str(exc)
    else:
        raise AssertionError("missing database configuration was accepted")


def test_web_origin_is_configurable_for_isolated_local_compose(monkeypatch) -> None:
    monkeypatch.setenv("CANCERJEV_WEB_ORIGIN", "http://localhost:23000")

    configured = Settings(_env_file=None)

    assert str(configured.web_origin).rstrip("/") == "http://localhost:23000"
