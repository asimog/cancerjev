"""CJ-R00 migration 0005: fencing columns, immutability triggers, publication uniqueness."""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

DATABASE_URL = os.getenv("CANCERJEV_DATABASE_URL")
pytestmark = [
    pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL URL is not configured"),
    pytest.mark.postgres,
    pytest.mark.integration,
]

LEGACY_SNAPSHOT = "sha256:" + "1" * 64
LEGACY_COHORT = "CO-legacy"
LEGACY_ANALYSIS = "11111111-1111-1111-1111-111111111111"
LEGACY_FINDING = "F-legacy"
LEGACY_RESULT = "sha256:" + "2" * 64


def run_alembic(direction: str, revision: str) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
    if direction == "upgrade":
        command.upgrade(config, revision)
    else:
        command.downgrade(config, revision)


def reset_schema() -> None:
    engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def seed_legacy_0004_rows() -> None:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO projects (project_id, name) VALUES ('TCGA-LUAD', 'legacy')")
        )
        connection.execute(
            text(
                "INSERT INTO dataset_snapshots (snapshot_id, snapshot_hash, project_id, provenance)"
                " VALUES ('DS-legacy', :hash, 'TCGA-LUAD', '{}'::jsonb)"
            ),
            {"hash": LEGACY_SNAPSHOT},
        )
        connection.execute(
            text(
                "INSERT INTO cohorts (cohort_id, snapshot_id, definition, case_ids, sample_ids,"
                " content_hash) VALUES (:cohort, 'DS-legacy', '{}'::jsonb, '[]'::jsonb,"
                " '[]'::jsonb, :content)"
            ),
            {"cohort": LEGACY_COHORT, "content": "sha256:" + "3" * 64},
        )
        connection.execute(
            text(
                "INSERT INTO analyses (analysis_id, snapshot_id, state, parameters)"
                " VALUES (:analysis, 'DS-legacy', 'completed', '{}'::jsonb)"
            ),
            {"analysis": LEGACY_ANALYSIS},
        )
        connection.execute(
            text(
                "INSERT INTO findings (finding_id, analysis_id, payload, snapshot_id, result_hash)"
                " VALUES (:finding, :analysis, '{\"legacy\": true}'::jsonb, 'DS-legacy', :result)"
            ),
            {"finding": LEGACY_FINDING, "analysis": LEGACY_ANALYSIS, "result": LEGACY_RESULT},
        )
    engine.dispose()


def test_upgrade_from_populated_0004_preserves_and_protects_legacy_rows():
    reset_schema()
    run_alembic("upgrade", "0004")
    seed_legacy_0004_rows()
    run_alembic("upgrade", "head")
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0005"
        assert connection.scalar(
            text("SELECT identity_version FROM dataset_snapshots WHERE snapshot_id = 'DS-legacy'")
        ) == 1
        assert (
            connection.scalar(
                text("SELECT result_hash FROM findings WHERE finding_id = :id"),
                {"id": LEGACY_FINDING},
            )
            == LEGACY_RESULT
        )
        with pytest.raises(DBAPIError):
            connection.execute(
                text("UPDATE cohorts SET definition = '{\"x\": 1}'::jsonb")
            )
        connection.rollback()
        with pytest.raises(DBAPIError):
            connection.execute(text("DELETE FROM findings"))
        connection.rollback()
        with pytest.raises(DBAPIError):
            connection.execute(
                text(
                    "INSERT INTO findings (finding_id, analysis_id, payload, snapshot_id,"
                    " result_hash) VALUES ('F-dup', :analysis, '{}'::jsonb, 'DS-legacy', :result)"
                ),
                {"analysis": LEGACY_ANALYSIS, "result": LEGACY_RESULT},
            )
        connection.rollback()
    engine.dispose()


def test_downgrade_roundtrip_never_discards_scientific_rows():
    reset_schema()
    run_alembic("upgrade", "head")
    seed_legacy_0004_rows()  # v2 columns already defaulted; rows remain v1-readable
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        before = connection.scalar(text("SELECT count(*) FROM findings"))
    engine.dispose()

    run_alembic("downgrade", "0004")
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0004"
        assert connection.scalar(text("SELECT count(*) FROM findings")) == before
        assert connection.scalar(text("SELECT count(*) FROM cohorts")) == 1
        # The R00 protections are gone at 0004, not silently weakened in place.
        connection.execute(text("UPDATE cohorts SET definition = '{\"x\": 1}'::jsonb"))
        assert connection.scalar(
            text("SELECT definition::text FROM cohorts WHERE cohort_id = :id"),
            {"id": LEGACY_COHORT},
        ).startswith('{"x"')
    engine.dispose()

    run_alembic("upgrade", "head")
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0005"
        assert connection.scalar(text("SELECT count(*) FROM findings")) == before
        with pytest.raises(DBAPIError):
            connection.execute(text("DELETE FROM cohorts"))
        connection.rollback()
    engine.dispose()
