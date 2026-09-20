import os
import threading

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from apps.api.main import app
from packages.database.models import AuditEvent, Cohort, DatasetObject, Job
from packages.database.session import session_factory
from packages.resources.service import (
    DurableResourceService,
    InvalidTransitionError,
    ResourceConflictError,
)
from packages.schemas.resources import (
    AnalysisCreate,
    ArtifactRegistration,
    CohortCreate,
    FindingCreate,
)
from packages.schemas.snapshot import SnapshotObject, SnapshotRecord

DATABASE_URL = os.getenv("CANCERJEV_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL URL is not configured")


@pytest.fixture(scope="module", autouse=True)
def migrated_database():
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
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_database(migrated_database):
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE idempotency_records, job_attempts, analyses, jobs, audit_events, "
                "findings, "
                "cohorts, snapshot_artifacts, snapshot_files, aliquots, samples, cases, "
                "dataset_snapshots, "
                "dataset_objects, projects CASCADE"
            )
        )
    engine.dispose()


@pytest.fixture
def factory():
    return session_factory(DATABASE_URL)


def artifact(role: str = "manifest", seed: str = "a") -> ArtifactRegistration:
    return ArtifactRegistration(
        sha256=f"sha256:{seed * 64}",
        size=10,
        media_type="application/octet-stream",
        logical_role=role,
        storage_backend="s3",
        storage_key=f"sha256/{seed}/{seed * 64}",
    )


def seed_snapshot(session: Session, snapshot_id: str = "DS-TCGA-LUAD-test") -> SnapshotRecord:
    snapshot = SnapshotRecord(
        snapshot_id=snapshot_id,
        snapshot_hash=f"sha256:{'1' * 64}",
        project_id="TCGA-LUAD",
        source_api="https://api.gdc.cancer.gov",
        gdc_release="42",
        query={"access": "open"},
        transformation_version="logical-v1",
        objects=(
            SnapshotObject(
                file_id="f1",
                file_name="x.tsv",
                file_size=1,
                md5sum="a" * 32,
                access="open",
            ),
        ),
    )
    DurableResourceService(session).register_snapshot(snapshot, [artifact()])
    return snapshot


def cohort_request() -> CohortCreate:
    return CohortCreate(
        snapshot_id="DS-TCGA-LUAD-test",
        definition={"sample_type": "Primary Tumor"},
        case_ids=["c2", "c1", "c1"],
        sample_ids=["s1"],
        exclusion_reasons={"normal": "excluded"},
        selection_policy_version="primary-v1",
    )


def test_project_snapshot_and_artifact_registry(factory) -> None:
    with factory.begin() as session:
        snapshot = seed_snapshot(session)
        service = DurableResourceService(session)
        duplicate = service.register_artifact(artifact(seed="a"))
        assert duplicate.sha256 == f"sha256:{'a' * 64}"
        assert service.projects.get("TCGA-LUAD") is not None
        assert service.snapshots.get(snapshot.snapshot_id).manifest_sha256 == duplicate.sha256
        assert session.scalar(select(func.count()).select_from(DatasetObject)) == 1


def test_cohort_identity_and_concurrent_creation(factory) -> None:
    with factory.begin() as session:
        seed_snapshot(session)
        first = DurableResourceService(session).create_cohort(cohort_request())
        repeated = DurableResourceService(session).create_cohort(cohort_request())
        assert first.cohort_id == repeated.cohort_id
        changed = DurableResourceService(session).create_cohort(
            cohort_request().model_copy(update={"selection_policy_version": "primary-v2"})
        )
        assert changed.cohort_id != first.cohort_id

    race_request = cohort_request().model_copy(update={"selection_policy_version": "primary-v3"})
    barrier = threading.Barrier(2)
    results: list[str] = []

    def create() -> None:
        with factory.begin() as session:
            barrier.wait()
            results.append(DurableResourceService(session).create_cohort(race_request).cohort_id)

    threads = [threading.Thread(target=create) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(set(results)) == 1
    assert results[0] not in {first.cohort_id, changed.cohort_id}
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Cohort)) == 3


def test_analysis_idempotency_lifecycle_finding_and_audit(factory) -> None:
    with factory.begin() as session:
        seed_snapshot(session)
        service = DurableResourceService(session)
        cohort = service.create_cohort(cohort_request())
        request = AnalysisCreate(
            snapshot_id="DS-TCGA-LUAD-test",
            cohort_id=cohort.cohort_id,
            engine="crossmodal",
            engine_version="1",
            parameters={"method": "welch"},
            expected_input_artifacts=[f"sha256:{'a' * 64}"],
        )
        analysis = service.create_analysis(request, "analysis-key-0001")
        repeated = service.create_analysis(request, "analysis-key-0001")
        assert repeated.analysis_id == analysis.analysis_id
        assert session.scalar(select(func.count()).select_from(Job)) == 1
        with pytest.raises(ResourceConflictError, match="different request"):
            service.create_analysis(
                request.model_copy(update={"engine_version": "2"}), "analysis-key-0001"
            )
        service.transition_analysis(str(analysis.analysis_id), "running")
        service.transition_analysis(str(analysis.analysis_id), "completed")
        with pytest.raises(InvalidTransitionError):
            service.transition_analysis(str(analysis.analysis_id), "running")
        finding = service.persist_finding(
            FindingCreate(
                finding_id="F-1",
                analysis_id=analysis.analysis_id,
                finding_type="mutation_rna",
                gene_id="ENSG1",
                gene_symbol="TP53",
                analysis_version="1",
                result_hash=f"sha256:{'b' * 64}",
                payload={"effect_size": 1.2},
            )
        )
        matches = service.findings.list(
            snapshot_id=None,
            cohort_id=None,
            analysis_id=None,
            finding_type="mutation_rna",
            gene="TP53",
            result_hash=finding.result_hash,
            limit=10,
            offset=0,
        )
        assert [value.finding_id for value in matches] == ["F-1"]
        assert session.scalar(select(func.count()).select_from(AuditEvent)) >= 6


def test_fk_rollback_and_matrix_rejection(factory) -> None:
    with factory.begin() as session:
        seed_snapshot(session)
    with factory() as session:
        with pytest.raises(IntegrityError), session.begin():
            session.add(
                Cohort(
                    cohort_id="bad",
                    snapshot_id="missing",
                    definition_version="1",
                    definition={},
                    case_ids=[],
                    sample_ids=[],
                    content_hash=f"sha256:{'c' * 64}",
                    exclusion_reasons={},
                    selection_policy_version="1",
                )
            )
        assert session.get(Cohort, "bad") is None
        session.rollback()
        with session.begin():
            service = DurableResourceService(session)
            cohort = service.create_cohort(cohort_request())
            with pytest.raises(ValueError, match="molecular data"):
                service.create_analysis(
                    AnalysisCreate(
                        snapshot_id="DS-TCGA-LUAD-test",
                        cohort_id=cohort.cohort_id,
                        engine="x",
                        engine_version="1",
                        parameters={"matrix": [[1, 2]]},
                    ),
                    "matrix-key-0001",
                )
        assert session.scalar(select(func.count()).select_from(Job)) == 0


def test_analysis_and_job_roll_back_together(factory, monkeypatch) -> None:
    with factory.begin() as session:
        seed_snapshot(session)
        cohort = DurableResourceService(session).create_cohort(cohort_request())

    def fail_analysis(_analysis):
        raise RuntimeError("injected analysis insert failure")

    with pytest.raises(RuntimeError, match="injected"), factory.begin() as session:
        service = DurableResourceService(session)
        monkeypatch.setattr(service.analyses, "save", fail_analysis)
        service.create_analysis(
            AnalysisCreate(
                snapshot_id="DS-TCGA-LUAD-test",
                cohort_id=cohort.cohort_id,
                engine="x",
                engine_version="1",
            ),
            "rollback-key-0001",
        )
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == 0


def test_immutable_registry_audit_and_published_snapshot(factory) -> None:
    with factory.begin() as session:
        seed_snapshot(session)
    statements = (
        "UPDATE dataset_objects SET size = 99",
        "UPDATE audit_events SET detail = 'changed'",
        "UPDATE dataset_snapshots SET status = 'failed'",
    )
    for statement in statements:
        with factory() as session, pytest.raises(DBAPIError), session.begin():
            session.execute(text(statement))


def test_resource_api_pagination_and_idempotency(factory) -> None:
    with factory.begin() as session:
        seed_snapshot(session)
        service = DurableResourceService(session)
        service.save_project("TCGA-BRCA", name="Breast")
        service.save_project("TCGA-COAD", name="Colon")
        cohort = service.create_cohort(cohort_request())
    request = {
        "snapshot_id": "DS-TCGA-LUAD-test",
        "cohort_id": cohort.cohort_id,
        "engine": "crossmodal",
        "engine_version": "1",
        "parameters": {},
        "expected_input_artifacts": [],
    }
    with TestClient(app) as client:
        page = client.get("/v1/projects", params={"limit": 1, "offset": 1})
        assert page.status_code == 200 and len(page.json()["items"]) == 1
        assert client.get("/v1/projects", params={"limit": 101}).status_code == 422
        first = client.post(
            "/v1/analyses", json=request, headers={"Idempotency-Key": "api-key-0001"}
        )
        second = client.post(
            "/v1/analyses", json=request, headers={"Idempotency-Key": "api-key-0001"}
        )
        assert first.status_code == second.status_code == 201
        assert first.json()["analysis_id"] == second.json()["analysis_id"]
        conflict = client.post(
            "/v1/analyses",
            json=request | {"engine_version": "2"},
            headers={"Idempotency-Key": "api-key-0001"},
        )
        assert conflict.status_code == 409
        assert client.get("/v1/snapshots/DS-TCGA-LUAD-test").status_code == 200
        assert client.get("/v1/artifacts/sha256:" + "a" * 64).status_code == 200
