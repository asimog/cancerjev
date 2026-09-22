"""Shared real-PostgreSQL schema lifecycle for integration modules."""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("CANCERJEV_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL URL is not configured")


@pytest.fixture(scope="session")
def migrated_database():
    """One migrated schema per test session: exercised chain plus current head."""
    engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
    command.upgrade(config, "0001")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001"
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0007"
    engine.dispose()
