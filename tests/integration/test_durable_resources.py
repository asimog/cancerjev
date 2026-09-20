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
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0003"
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


@pytest.fixture
def materialization_context(factory, gdc_fixture, tmp_path):
    from packages.resources.materialization import MaterializationService
    from packages.schemas.identity import AliquotRecord, CaseRecord, FileSampleLink, SampleRecord
    from packages.storage.config import StorageSettings
    from packages.storage.objects import FileObjectStore, object_key
    from packages.storage.parquet import write_records

    settings = StorageSettings(
        object_root=tmp_path / "objects", snapshot_root=tmp_path / "snapshots"
    )
    store = FileObjectStore(settings.object_root)
    names = ("mutation.maf", "rna.tsv", "gene_cnv.tsv", "segment.tsv", "clinical.json")
    contexts = [gdc_fixture(name) for name in names]
    cases, samples, aliquots, links = {}, {}, {}, {}
    for _, _, identity in contexts:
        cases.update({c.case_id: c for c in identity.cases})
        samples.update({s.sample_id: s for s in identity.samples})
        aliquots.update({a.aliquot_id: a for a in identity.aliquots})
        links.update({(v.file_id, v.case_id, v.sample_id, v.aliquot_id): v for v in identity.links})
    snapshot = SnapshotRecord(
        snapshot_id="DS-TCGA-LUAD-parsers",
        snapshot_hash="sha256:" + "8" * 64,
        project_id="TCGA-LUAD",
        source_api="https://api.gdc.cancer.gov",
        gdc_release="fixture",
        query={},
        transformation_version="logical-v1",
        objects=tuple(source for _, source, _ in contexts if source),
        case_ids=tuple(sorted(cases)),
        sample_ids=tuple(sorted(samples)),
        aliquot_ids=tuple(sorted(aliquots)),
    )
    registrations = []
    for role, records, model in (
        ("cases", cases, CaseRecord),
        ("samples", samples, SampleRecord),
        ("aliquots", aliquots, AliquotRecord),
        ("identity_links", links, FileSampleLink),
    ):
        path = tmp_path / (role + ".parquet")
        write_records(list(records.values()), path, model=model)
        digest = store.put_file(path)
        registrations.append(
            ArtifactRegistration(
                sha256=digest,
                size=path.stat().st_size,
                media_type="application/vnd.apache.parquet",
                logical_role=role,
                storage_backend="filesystem",
                storage_key=object_key(digest),
            )
        )
    raw = snapshot.model_dump_json().encode()
    digest = store.put(raw)
    registrations.append(
        ArtifactRegistration(
            sha256=digest,
            size=len(raw),
            media_type="application/json",
            logical_role="snapshot",
            storage_backend="filesystem",
            storage_key=object_key(digest),
        )
    )
    with factory.begin() as session:
        DurableResourceService(session).register_snapshot(snapshot, registrations)
    return snapshot, store, settings, contexts, MaterializationService


@pytest.mark.parametrize(
    "name,modality,measurement",
    [
        ("mutation.maf", "mutation", ""),
        ("rna.tsv", "expression", "tpm_unstranded"),
        ("gene_cnv.tsv", "cnv", ""),
        ("segment.tsv", "segment_cnv", ""),
        ("clinical.json", "clinical", ""),
    ],
)
def test_durable_fixture_flow(
    factory, materialization_context, gdc_fixture, name, modality, measurement
):
    import pyarrow.parquet as pq

    from packages.database.models import Materialization
    from packages.schemas.materialization import MaterializationRequest

    snapshot, store, settings, _, service_type = materialization_context
    path, source, _ = gdc_fixture(name)
    with factory.begin() as session:
        resources = DurableResourceService(session)
        service = service_type(resources, store, settings)
        binding = service.register_local_source(
            snapshot.snapshot_id,
            path,
            file_id=source.file_id if source else None,
            clinical_provenance={
                "endpoint": "https://api.gdc.cancer.gov/cases",
                "query": {"size": 1},
                "acquired_at": "2026-09-20T00:00:00Z",
            }
            if source is None
            else None,
        )
        request = MaterializationRequest(
            snapshot_id=snapshot.snapshot_id,
            source_id=binding.source_id,
            expected_source_sha256=binding.sha256,
            modality=modality,
            measurement_type=measurement,
        )
    # Simulate the durable worker boundary: a new DB transaction resolves all state.
    with factory.begin() as session:
        service = service_type(DurableResourceService(session), store, settings)
        first = service.run(request, batch_size=2)
    with factory.begin() as session:
        resources = DurableResourceService(session)
        repeated = service_type(resources, store, settings).run(request, batch_size=3)
        assert repeated == first
        assert session.scalar(select(func.count()).select_from(Materialization)) == 1
        found = resources.list_materializations(snapshot.snapshot_id, modality, measurement)
        assert len(found) == 1 and found[0].row_count > 0
        output = settings.object_root / "inspect.parquet"
        store.stage(found[0].output_sha256, output)
        assert pq.ParquetFile(output).metadata.num_rows == found[0].row_count
        assert resources.snapshots.get(snapshot.snapshot_id).snapshot_hash == snapshot.snapshot_hash
        assert found[0].parser_version == "1" and found[0].schema_version == "2"
        with pytest.raises(ResourceConflictError, match="source/snapshot/hash"):
            service_type(resources, store, settings).run(
                request.model_copy(update={"expected_source_sha256": "sha256:" + "0" * 64})
            )


def test_materialization_race_and_parser_version(
    factory, materialization_context, gdc_fixture, monkeypatch
):
    from dataclasses import replace

    import packages.gdc.parsers as parsers
    from packages.database.models import Materialization
    from packages.schemas.materialization import MaterializationRequest

    snapshot, store, settings, _, service_type = materialization_context
    path, source, _ = gdc_fixture("rna.tsv")
    with factory.begin() as session:
        binding = service_type(
            DurableResourceService(session), store, settings
        ).register_local_source(snapshot.snapshot_id, path, file_id=source.file_id)
    request = MaterializationRequest(
        snapshot_id=snapshot.snapshot_id,
        source_id=binding.source_id,
        expected_source_sha256=binding.sha256,
        modality="expression",
        measurement_type="tpm_unstranded",
    )
    barrier = threading.Barrier(2)
    results, errors = [], []

    def run():
        try:
            with factory.begin() as session:
                barrier.wait(timeout=10)
                results.append(
                    service_type(DurableResourceService(session), store, settings).run(request)
                )
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not errors and len(results) == 2 and results[0] == results[1]
    new_parser = replace(
        next(p for p in parsers.PARSERS if p.modality == "expression"), version="2"
    )
    monkeypatch.setattr(parsers, "PARSERS", parsers.PARSERS + (new_parser,))
    with factory.begin() as session:
        second = service_type(DurableResourceService(session), store, settings).run(
            request.model_copy(update={"parser_version": "2"})
        )
        assert second["materialization_id"] != results[0]["materialization_id"]
        assert second["logical_sha256"] == results[0]["logical_sha256"]
        assert second["output_sha256"] == results[0]["output_sha256"]
        assert session.scalar(select(func.count()).select_from(Materialization)) == 2


def test_source_binding_checks_and_rollback(
    factory, materialization_context, gdc_fixture, monkeypatch
):
    from packages.database.models import Materialization
    from packages.schemas.materialization import MaterializationRequest

    snapshot, store, settings, _, service_type = materialization_context
    path, source, _ = gdc_fixture("rna.tsv")
    with factory.begin() as session:
        resources = DurableResourceService(session)
        service = service_type(resources, store, settings)
        with pytest.raises(ValueError, match="not in frozen"):
            service.register_local_source(snapshot.snapshot_id, path, file_id="absent")
        binding = service.register_local_source(snapshot.snapshot_id, path, file_id=source.file_id)
    request = MaterializationRequest(
        snapshot_id=snapshot.snapshot_id,
        source_id=binding.source_id,
        expected_source_sha256=binding.sha256,
        modality="expression",
        measurement_type="tpm_unstranded",
    )

    def fail_audit(*args):
        raise RuntimeError("injected registration failure")

    with pytest.raises(RuntimeError, match="injected"), factory.begin() as session:
        resources = DurableResourceService(session)
        monkeypatch.setattr(resources, "_audit", fail_audit)
        service_type(resources, store, settings).run(request)
    with factory.begin() as session:
        assert session.scalar(select(func.count()).select_from(Materialization)) == 0
        assert (
            service_type(DurableResourceService(session), store, settings).run(request)["row_count"]
            > 0
        )
    with factory.begin() as session, pytest.raises(DBAPIError):
        session.execute(text("UPDATE materializations SET parser_version = 'corrupt'"))


def test_migration_0003_roundtrip_preserves_pr7(factory):
    with factory.begin() as session:
        snapshot = seed_snapshot(session)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
    command.downgrade(config, "0002")
    with factory() as session:
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
        assert DurableResourceService(session).snapshots.get(snapshot.snapshot_id) is not None
    command.upgrade(config, "head")
    with factory() as session:
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == "0003"
        assert session.scalar(text("SELECT count(*) FROM materializations")) == 0
        assert DurableResourceService(session).snapshots.get(snapshot.snapshot_id) is not None


def test_worker_uses_compact_persisted_context(
    factory, materialization_context, gdc_fixture, monkeypatch
):
    from workers.ingest.materialize import materialize_snapshot

    snapshot, store, settings, _, service_type = materialization_context
    path, source, _ = gdc_fixture("rna.tsv")
    with factory.begin() as session:
        binding = service_type(
            DurableResourceService(session), store, settings
        ).register_local_source(snapshot.snapshot_id, path, file_id=source.file_id)
    monkeypatch.setenv("CANCERJEV_OBJECT_ROOT", str(settings.object_root))
    result = materialize_snapshot(
        {
            "snapshot_id": snapshot.snapshot_id,
            "source_id": binding.source_id,
            "expected_source_sha256": binding.sha256,
            "modality": "expression",
            "measurement_type": "tpm_unstranded",
        }
    )
    assert result["row_count"] == 4 and not any("path" in key for key in result)


def test_existing_pr7_snapshot_paths(factory, gdc_fixture, tmp_path):
    import asyncio
    import json

    from apps.api.main import _snapshot_artifacts
    from packages.resources.materialization import MaterializationService
    from packages.schemas.materialization import MaterializationRequest
    from packages.schemas.snapshot import LogicalSnapshotRequest
    from packages.storage.config import StorageSettings
    from packages.storage.snapshots import FileSnapshotRepository
    from workers.ingest.snapshot import LogicalSnapshotService

    path, source, _ = gdc_fixture("rna.tsv")
    hit = json.loads(path.with_name("rna.tsv.metadata.json").read_text())["source"]
    hit.update(file_name=source.file_name, file_size=source.file_size, md5sum=source.md5sum)

    class FrozenClient:
        base_url = "https://api.gdc.cancer.gov"

        async def get_open_files(self, *args, **kwargs):
            return {"data": {"hits": [hit]}}

    settings = StorageSettings(
        object_root=tmp_path / "objects", snapshot_root=tmp_path / "snapshots"
    )
    snapshot = asyncio.run(
        LogicalSnapshotService(
            client=FrozenClient(),
            repository=FileSnapshotRepository(settings.snapshot_root),
        ).create(LogicalSnapshotRequest(project_id="TCGA-LUAD"))
    )
    with factory.begin() as session:
        resources = DurableResourceService(session)
        resources.register_snapshot(snapshot, _snapshot_artifacts(settings.snapshot_root, snapshot))
        service = MaterializationService(resources, settings.store(), settings)
        binding = service.register_local_source(snapshot.snapshot_id, path, file_id=source.file_id)
        result = service.run(
            MaterializationRequest(
                snapshot_id=snapshot.snapshot_id,
                source_id=binding.source_id,
                expected_source_sha256=binding.sha256,
                modality="expression",
                measurement_type="unstranded",
            )
        )
        assert result["row_count"] == 4


def test_clinical_source_retry_ignores_acquisition_clock(
    factory, materialization_context, gdc_fixture
):
    snapshot, store, settings, _, service_type = materialization_context
    path, _, _ = gdc_fixture("clinical.json")
    provenance = {
        "endpoint": "https://api.gdc.cancer.gov/cases",
        "query": {"size": 1},
        "acquired_at": "2026-09-20T00:00:00Z",
    }
    with factory.begin() as session:
        service = service_type(DurableResourceService(session), store, settings)
        first = service.register_local_source(
            snapshot.snapshot_id, path, clinical_provenance=provenance
        )
        second = service.register_local_source(
            snapshot.snapshot_id, path, clinical_provenance=provenance | {"acquired_at": "later"}
        )
        assert first.source_id == second.source_id
        assert second.source_metadata["provenance"]["acquired_at"] == provenance["acquired_at"]


def test_clinical_acquisition_registration_and_materialization(factory, materialization_context):
    import asyncio
    import json

    import httpx

    from packages.gdc.client import GDCClient
    from packages.schemas.materialization import MaterializationRequest

    snapshot, store, settings, _, service_type = materialization_context

    def respond(request):
        members = json.loads(request.url.params["filters"])["content"]["value"]
        return httpx.Response(
            200,
            json={
                "data": {
                    "hits": [{"case_id": c} for c in members],
                    "pagination": {"total": len(members)},
                }
            },
        )

    async def acquire(service):
        async with httpx.AsyncClient(
            base_url="https://api.gdc.cancer.gov", transport=httpx.MockTransport(respond)
        ) as http:
            client = GDCClient("https://api.gdc.cancer.gov", client=http)
            return [s async for s in service.acquire_clinical_sources(snapshot.snapshot_id, client)]

    with factory.begin() as session:
        service = service_type(DurableResourceService(session), store, settings)
        sources = asyncio.run(acquire(service))
        assert len(sources) == 1
        source = sources[0]
        result = service.run(
            MaterializationRequest(
                snapshot_id=snapshot.snapshot_id,
                source_id=source.source_id,
                expected_source_sha256=source.sha256,
                modality="clinical",
            )
        )
        assert result["row_count"] == len(snapshot.case_ids)
