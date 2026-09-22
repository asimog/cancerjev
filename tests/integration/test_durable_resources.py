import os
import threading
import uuid

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from apps.api.main import app
from packages.database.models import Analysis, AuditEvent, Cohort, DatasetObject, Finding, Job
from packages.database.session import session_factory
from packages.provenance.hashing import canonical_hash
from packages.resources.service import (
    DurableResourceService,
    InvalidTransitionError,
    ResourceConflictError,
)
from packages.schemas.resources import (
    AnalysisCreate,
    ArtifactRegistration,
    CohortCreate,
)
from packages.schemas.snapshot import SnapshotObject, SnapshotRecord

DATABASE_URL = os.getenv("CANCERJEV_DATABASE_URL")
pytestmark = [
    pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL URL is not configured"),
    pytest.mark.postgres,
    pytest.mark.integration,
]


@pytest.fixture(autouse=True)
def clean_database(migrated_database, tmp_path, monkeypatch):
    monkeypatch.setenv("CANCERJEV_OBJECT_BACKEND", "filesystem")
    monkeypatch.setenv("CANCERJEV_OBJECT_ROOT", str(tmp_path / "objects"))
    monkeypatch.setenv("CANCERJEV_SNAPSHOT_ROOT", str(tmp_path / "snapshots"))
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
        snapshot_hash=canonical_hash({"test_snapshot": snapshot_id}),
        project_id="TCGA-LUAD",
        source_api="https://api.gdc.cancer.gov",
        gdc_release="42",
        query={"access": "open"},
        transformation_version="logical-v1",
        case_ids=("c1", "c2"),
        sample_ids=("s1", "s2"),
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
    # Lifecycle fixtures now supply the actual immutable graph required by cohorts.
    import tempfile
    from pathlib import Path

    from packages.schemas.identity import AliquotRecord, CaseRecord, FileSampleLink, SampleRecord
    from packages.storage.config import StorageSettings
    from packages.storage.objects import object_key
    from packages.storage.parquet import write_records

    store = StorageSettings().store()
    registrations = [artifact()]
    with tempfile.TemporaryDirectory() as tmp:
        for role, records, model in (
            (
                "cases",
                [CaseRecord(case_id=c, project_id="TCGA-LUAD") for c in ("c1", "c2")],
                CaseRecord,
            ),
            (
                "samples",
                [
                    SampleRecord(sample_id="s1", case_id="c1"),
                    SampleRecord(sample_id="s2", case_id="c2"),
                ],
                SampleRecord,
            ),
            ("aliquots", [], AliquotRecord),
            (
                "identity_links",
                [FileSampleLink(file_id="f1", case_id="c1", sample_id="s1")],
                FileSampleLink,
            ),
        ):
            path = Path(tmp) / (role + ".parquet")
            write_records(records, path, model=model)
            raw = path.read_bytes()
            digest = store.put(raw)
            registrations.append(
                ArtifactRegistration(
                    sha256=digest,
                    size=len(raw),
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
    DurableResourceService(session).register_snapshot(snapshot, registrations)
    return snapshot


def seed_analysis_input(
    session,
    snapshot_id="DS-TCGA-LUAD-test",
    seed="d",
    *,
    modality="expression",
    output_seed="b",
    diagnostics_seed="c",
):
    service = DurableResourceService(session)
    source = service.register_source(
        snapshot_id=snapshot_id,
        artifact=artifact("test_source", "e"),
        source_file_id="f1",
        source_metadata={"kind": "synthetic-test"},
    )
    materialization_id = "sha256:" + seed * 64
    service.register_materialization(
        metadata=dict(
            materialization_id=materialization_id,
            snapshot_id=snapshot_id,
            source_id=source.source_id,
            output_sha256="sha256:" + output_seed * 64,
            diagnostics_sha256="sha256:" + diagnostics_seed * 64,
            modality=modality,
            measurement_type="tpm_unstranded" if modality == "expression" else "",
            parser_name="test-fixture",
            parser_version="1",
            schema_version="2",
            normalization_version="1",
            selection_version="1",
            logical_sha256="sha256:" + "f" * 64,
            row_count=1,
            diagnostics_summary={},
        ),
        output=artifact("canonical_" + modality, output_seed),
        diagnostics=artifact("diagnostics", diagnostics_seed),
    )
    return dict(
        materialization_id=materialization_id,
        modality=modality,
        measurement_type="tpm_unstranded" if modality == "expression" else "",
    )


def seed_cnv_rna_inputs(session):
    return [
        seed_analysis_input(
            session,
            "DS-TCGA-LUAD-test",
            "6",
            modality="cnv",
            output_seed="7",
            diagnostics_seed="8",
        ),
        seed_analysis_input(session),
    ]


def cohort_request() -> CohortCreate:
    return CohortCreate(
        snapshot_id="DS-TCGA-LUAD-test",
        definition={"sample_type": "Primary Tumor"},
        case_ids=["c2", "c1", "c1"],
        sample_ids=["s1"],
        exclusion_reasons={"normal": "excluded"},
        selection_policy_version="primary-v1",
    )


def finding_payload(gene: str = "ENSG1", family: tuple[str, ...] = ("ENSG1",)):
    from packages.schemas.finding import Finding as FindingPayload

    return FindingPayload(
        snapshot_id="DS-TCGA-LUAD-test",
        finding_type="cnv_expression_association",
        gene=gene,
        cohort_size=2,
        eligible_cases=1,
        eligible_case_ids=("c1",),
        eligible_sample_ids=("s1",),
        n_effective=1,
        effect_size=0.5,
        confidence_interval=(0.1, 0.9),
        p_value=0.01,
        q_value=0.02,
        missing_n=1,
        missing_fraction=0.5,
        analysis_version="cnv-rna-v1",
        input_object_hashes=(f"sha256:{'b' * 64}",),
        tested_gene_ids=family,
        result_hash=f"sha256:{'d' * 64}",
    )


def cnv_rna_analysis(service: DurableResourceService, key: str) -> Analysis:
    cohort = service.create_cohort(cohort_request())
    return service.create_analysis(
        AnalysisCreate(
            snapshot_id="DS-TCGA-LUAD-test",
            cohort_id=cohort.cohort_id,
            engine="cnv_rna",
            engine_version="1",
            input_materializations=seed_cnv_rna_inputs(service.session),
        ),
        key,
    )


@pytest.mark.parametrize(
    "cases,samples",
    [
        (["foreign-case"], []),
        (["c1"], ["foreign-sample"]),
        (["c2"], ["s1"]),
        ([], ["s1"]),
    ],
)
def test_cohort_rejects_non_snapshot_or_impossible_membership(factory, cases, samples):
    with factory.begin() as session:
        seed_snapshot(session)
        service = DurableResourceService(session)
        with pytest.raises(ResourceConflictError, match="cohort"):
            service.create_cohort(
                cohort_request().model_copy(update={"case_ids": cases, "sample_ids": samples})
            )
        assert session.scalar(select(func.count()).select_from(Cohort)) == 0


def test_analysis_requires_materialization_lineage_and_exact_contract(factory):
    with factory.begin() as session:
        seed_snapshot(session)
        seed_snapshot(session, "DS-other")
        service = DurableResourceService(session)
        cohort = service.create_cohort(cohort_request())
        valid = seed_analysis_input(session)
        other = seed_analysis_input(session, "DS-other", "9")
        base = dict(
            snapshot_id=cohort.snapshot_id,
            cohort_id=cohort.cohort_id,
            engine="crossmodal",
            engine_version="1",
        )
        with pytest.raises(ValueError):
            AnalysisCreate(**base, expected_input_artifacts=["sha256:" + "a" * 64])
        for invalid in (
            other,
            valid | {"modality": "mutation"},
            valid | {"measurement_type": "unstranded"},
        ):
            with pytest.raises(ResourceConflictError, match="mismatch"):
                service.create_analysis(
                    AnalysisCreate(**base, input_materializations=[invalid]), "rejected-input"
                )
        with pytest.raises(ResourceConflictError, match="hashes"):
            service.create_analysis(
                AnalysisCreate(
                    **base,
                    input_materializations=[valid],
                    expected_input_artifacts=["sha256:" + "a" * 64],
                ),
                "rejected-hash",
            )
        assert session.scalar(select(func.count()).select_from(Job)) == 0
        result = service.create_analysis(
            AnalysisCreate(**base, input_materializations=[valid]), "valid-input"
        )
        assert result.input_materializations == [valid]

        with pytest.raises(ResourceConflictError, match="exactly one|duplicate|modality"):
            service.create_analysis(
                AnalysisCreate(
                    **(base | {"engine": "cnv_rna"}),
                    input_materializations=[valid, valid],
                ),
                "duplicate-modality-input",
            )
        assert result.expected_input_artifacts == ["sha256:" + "b" * 64]


def test_frozen_links_and_analysis_inputs_cannot_be_mutated(factory):
    with factory.begin() as session:
        seed_snapshot(session)
        service = DurableResourceService(session)
        cohort = service.create_cohort(cohort_request())
        service.create_analysis(
            AnalysisCreate(
                snapshot_id=cohort.snapshot_id,
                cohort_id=cohort.cohort_id,
                engine="x",
                engine_version="1",
                input_materializations=[seed_analysis_input(session)],
            ),
            "immutable-inputs",
        )
    for statement in (
        "UPDATE snapshot_artifacts SET sha256 = 'sha256:" + "a" * 64 + "'",
        "DELETE FROM snapshot_artifacts",
        "UPDATE analyses SET input_materializations = '[]'::jsonb",
        "UPDATE analyses SET expected_input_artifacts = '[]'::jsonb",
    ):
        with factory.begin() as session, pytest.raises(DBAPIError):
            session.execute(text(statement))


def test_manifest_resolves_durable_snapshot_and_rejects_uuid_before_network(factory):
    import asyncio
    from unittest.mock import AsyncMock

    import httpx

    from packages.gdc.client import GDCClient
    from packages.gdc.manifest import generate_manifest
    from packages.schemas.identity import FileRecord

    with factory.begin() as session:
        snapshot = seed_snapshot(session)
        raw = generate_manifest([FileRecord(**snapshot.objects[0].model_dump())])
        send = AsyncMock(return_value=httpx.Response(200, content=raw))

        async def run():
            async with GDCClient("https://api.gdc.cancer.gov") as client:
                client._request = send
                service = DurableResourceService(session)
                with pytest.raises(ValueError, match="subset"):
                    await service.manifest(snapshot.snapshot_id, client, ["unknown-uuid"])
                send.assert_not_called()
                assert await service.manifest(snapshot.snapshot_id, client, ["f1"]) == raw
                send.assert_called_once()

        asyncio.run(run())


def reference_unreferenced_objects(snapshot_id: str) -> None:
    """Attach a reference to every orphan object so a guarded 0006 downgrade can restore it."""
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO snapshot_artifacts"
                " (snapshot_id, logical_role, sha256, storage_backend, storage_key)"
                " SELECT :snapshot, 'test-object:' || obj.sha256, obj.sha256, 'filesystem',"
                " 'test/' || obj.sha256"
                " FROM dataset_objects obj"
                " WHERE NOT EXISTS ("
                "   SELECT 1 FROM snapshot_artifacts sa WHERE sa.sha256 = obj.sha256)"
            ),
            {"snapshot": snapshot_id},
        )
    engine.dispose()


def test_migration_0004_roundtrip_preserves_historical_analysis(factory):
    with factory.begin() as session:
        seed_snapshot(session)
        service = DurableResourceService(session)
        cohort = service.create_cohort(cohort_request())
        analysis = service.create_analysis(
            AnalysisCreate(
                snapshot_id=cohort.snapshot_id,
                cohort_id=cohort.cohort_id,
                engine="x",
                engine_version="1",
                input_materializations=[seed_analysis_input(session)],
            ),
            "migration-inputs",
        )
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
    # Materialization sources and diagnostics carry no snapshot reference, so the
    # guarded 0006 downgrade refuses to fabricate their locators.
    with pytest.raises(RuntimeError, match="no snapshot_artifacts reference"):
        command.downgrade(config, "0003")
    reference_unreferenced_objects("DS-TCGA-LUAD-test")
    command.downgrade(config, "0003")
    command.upgrade(config, "head")
    with factory() as session:
        restored = DurableResourceService(session).analyses.get(str(analysis.analysis_id))
        assert restored.expected_input_artifacts == ["sha256:" + "b" * 64]
        assert restored.input_materializations == []  # No fabricated backfill of lost lineage.


def test_project_snapshot_and_artifact_registry(factory) -> None:
    with factory.begin() as session:
        snapshot = seed_snapshot(session)
        service = DurableResourceService(session)
        duplicate = service.register_artifact(artifact(seed="a"))
        assert duplicate.sha256 == f"sha256:{'a' * 64}"
        assert service.projects.get("TCGA-LUAD") is not None
        assert service.snapshots.get(snapshot.snapshot_id).manifest_sha256 == duplicate.sha256
        assert (
            session.scalar(
                select(func.count())
                .select_from(DatasetObject)
                .where(DatasetObject.sha256 == duplicate.sha256)
            )
            == 1
        )


def test_artifact_reference_owns_role_and_locator(factory) -> None:
    """Same bytes under two roles keep each reference's own role and storage location."""
    shared = "sha256:" + "9" * 64
    snapshot = SnapshotRecord(
        snapshot_id="DS-ref-owner",
        snapshot_hash=canonical_hash({"ref": "owner"}),
        project_id="TCGA-LUAD",
        source_api="https://api.gdc.cancer.gov",
        gdc_release="fixture",
        query={"access": "open"},
        transformation_version="logical-v1",
        objects=(),
    )
    registrations = [
        ArtifactRegistration(
            sha256=shared,
            size=10,
            media_type="application/octet-stream",
            logical_role="manifest",
            storage_backend="filesystem",
            storage_key="legacy/manifest.tsv",
        ),
        ArtifactRegistration(
            sha256=shared,
            size=10,
            media_type="application/octet-stream",
            logical_role="provenance",
            storage_backend="filesystem",
            storage_key="legacy/provenance.json",
        ),
    ]
    with factory.begin() as session:
        service = DurableResourceService(session)
        service.register_snapshot(snapshot, registrations)
        references = {
            reference.logical_role: reference
            for reference in service.artifacts.list_for_snapshot(snapshot.snapshot_id)
        }
    assert set(references) == {"manifest", "provenance"}
    assert references["manifest"].storage_key == "legacy/manifest.tsv"
    assert references["provenance"].storage_key == "legacy/provenance.json"
    assert {reference.sha256 for reference in references.values()} == {shared}


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
    from packages.schemas import resources as resources_schemas
    from packages.schemas.finding import Finding as FindingPayload

    with factory.begin() as session:
        seed_snapshot(session)
        service = DurableResourceService(session)
        cohort = service.create_cohort(cohort_request())
        request = AnalysisCreate(
            snapshot_id="DS-TCGA-LUAD-test",
            cohort_id=cohort.cohort_id,
            engine="cnv_rna",
            engine_version="1",
            parameters={"method": "welch"},
            expected_input_artifacts=[f"sha256:{'7' * 64}", f"sha256:{'b' * 64}"],
            input_materializations=seed_cnv_rna_inputs(session),
        )
        analysis = service.create_analysis(request, "analysis-key-0001")
        repeated = service.create_analysis(request, "analysis-key-0001")
        assert repeated.analysis_id == analysis.analysis_id
        assert session.scalar(select(func.count()).select_from(Job)) == 1
        with pytest.raises(ResourceConflictError, match="different request"):
            service.create_analysis(
                request.model_copy(update={"engine_version": "2"}), "analysis-key-0001"
            )

        # Caller-authored Finding identity no longer exists on any surface.
        assert not hasattr(service, "persist_finding")
        assert not hasattr(resources_schemas, "FindingCreate")

        payload = FindingPayload(
            snapshot_id="DS-TCGA-LUAD-test",
            finding_type="cnv_expression_association",
            gene="ENSG1",
cohort_size=2,
            eligible_cases=1,
            eligible_case_ids=("c1",),
            eligible_sample_ids=("s1",),
            n_effective=1,
            effect_size=0.5,
            confidence_interval=(0.1, 0.9),
            p_value=0.01,
            q_value=0.02,
            missing_n=1,
            missing_fraction=0.5,
            analysis_version="cnv-rna-v1",
            input_object_hashes=(f"sha256:{'b' * 64}",),
            tested_gene_ids=("ENSG1",),
            result_hash=f"sha256:{'d' * 64}",
        )
        # A queued analysis cannot publish; publication happens while running.
        with pytest.raises(ResourceConflictError, match="running"):
            service.publish_findings(analysis, [payload])
        service.transition_analysis(str(analysis.analysis_id), "running")
        published = service.publish_findings(analysis, [payload])
        assert published[0].result_hash != payload.result_hash
        assert published[0].finding_id.startswith("F-")
        assert len(published[0].finding_id.removeprefix("F-")) == 32
        assert ":" not in published[0].finding_id
        expected_id = published[0].finding_id
        assert published[0].finding_id == expected_id
        assert published[0].gene_id == "ENSG1" and published[0].snapshot_id == analysis.snapshot_id
        # Idempotent republication converges on the same authoritative row.
        again = service.publish_findings(analysis, [payload])
        assert again[0].finding_id == published[0].finding_id
        assert session.scalar(select(func.count()).select_from(Finding)) == 1
        service.transition_analysis(str(analysis.analysis_id), "completed")
        with pytest.raises(InvalidTransitionError):
            service.transition_analysis(str(analysis.analysis_id), "running")
        with pytest.raises(ResourceConflictError, match="running"):
            service.publish_findings(analysis, [payload])
        matches = service.findings.list(
            snapshot_id=None,
            cohort_id=None,
            analysis_id=None,
            finding_type="cnv_expression_association",
            gene=None,
            result_hash=published[0].result_hash,
            limit=10,
            offset=0,
        )
        assert [value.finding_id for value in matches] == [expected_id]
        assert session.scalar(select(func.count()).select_from(AuditEvent)) >= 6


def test_publication_requires_engine_declared_tested_family(factory) -> None:
    with factory.begin() as session:
        seed_snapshot(session)
        service = DurableResourceService(session)
        analysis = cnv_rna_analysis(service, "family-key-0001")
        service.transition_analysis(str(analysis.analysis_id), "running")
        family = ("ENSG1", "ENSG2")
        declared = finding_payload("ENSG1", family)
        # A batch truncated below the engine-declared family must not be signed.
        with pytest.raises(ResourceConflictError, match="tested universe"):
            service.publish_findings(analysis, [declared])
        published = service.publish_findings(analysis, [declared, finding_payload("ENSG2", family)])
        assert {row.gene_id for row in published} == {"ENSG1", "ENSG2"}
        assert session.scalar(select(func.count()).select_from(Finding)) == 2


def test_snapshot_registration_rejects_duplicate_roles(factory) -> None:
    snapshot = SnapshotRecord(
        snapshot_id="DS-duplicate-role",
        snapshot_hash=canonical_hash({"duplicate": "role"}),
        project_id="TCGA-LUAD",
        source_api="https://api.gdc.cancer.gov",
        gdc_release="fixture",
        query={"access": "open"},
        transformation_version="logical-v1",
        objects=(),
    )
    registrations = [artifact("manifest", "a"), artifact("manifest", "b")]
    with factory.begin() as session, pytest.raises(ResourceConflictError, match="duplicate"):
        DurableResourceService(session).register_snapshot(snapshot, registrations)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(DatasetObject)) == 0


def test_findings_gene_filter_matches_published_finding(factory) -> None:
    with factory.begin() as session:
        seed_snapshot(session)
        service = DurableResourceService(session)
        analysis = cnv_rna_analysis(service, "gene-filter-key-0001")
        service.transition_analysis(str(analysis.analysis_id), "running")
        published = service.publish_findings(analysis, [finding_payload("ENSG1")])
        expected = published[0].finding_id
    with TestClient(app) as client:
        response = client.get("/v1/findings", params={"gene": "ENSG1"})
        assert response.status_code == 200
        items = response.json()["items"]
        assert [item["finding_id"] for item in items] == [expected]
        assert items[0]["gene_id"] == "ENSG1"
        assert client.get("/v1/findings", params={"gene": "ENSG2"}).json()["items"] == []


def test_requested_analysis_can_transition_to_running_and_failed(factory) -> None:
    with factory.begin() as session:
        seed_snapshot(session)
        cohort = DurableResourceService(session).create_cohort(cohort_request())
        legacy = Analysis(
            analysis_id=uuid.uuid4(),
            snapshot_id="DS-TCGA-LUAD-test",
            cohort_id=cohort.cohort_id,
            engine="cnv_rna",
            engine_version="1",
            state="requested",
            parameters={},
            expected_input_artifacts=[],
            input_materializations=[],
        )
        session.add(legacy)
        session.flush()
        service = DurableResourceService(session)
        service.transition_analysis(str(legacy.analysis_id), "running")
        assert legacy.started_at is not None
        service.transition_analysis(
            str(legacy.analysis_id), "failed", error="legacy input unavailable"
        )
        assert legacy.state == "failed"


def test_completed_result_reports_every_published_finding(factory) -> None:
    from packages.resources.execution import AnalysisExecutionService

    with factory.begin() as session:
        seed_snapshot(session)
        service = DurableResourceService(session)
        analysis = cnv_rna_analysis(service, "completed-result-key-0001")
        service.transition_analysis(str(analysis.analysis_id), "running")
        family = tuple(f"ENSG{i:05d}" for i in range(1001))
        payloads = [finding_payload(gene, family) for gene in family]
        assert len(service.publish_findings(analysis, payloads)) == 1001
        service.transition_analysis(str(analysis.analysis_id), "completed")
        analysis_id = analysis.analysis_id
    with factory() as session:
        result = AnalysisExecutionService._completed_result(
            session, session.get(Analysis, analysis_id)
        )
    assert result["published"] == 1001
    assert len(result["finding_ids"]) == 1001


def test_findings_and_cohorts_are_database_immutable(factory) -> None:
    from packages.schemas.finding import Finding as FindingPayload

    with factory.begin() as session:
        seed_snapshot(session)
        service = DurableResourceService(session)
        cohort = service.create_cohort(cohort_request())
        analysis = service.create_analysis(
            AnalysisCreate(
                snapshot_id="DS-TCGA-LUAD-test",
                cohort_id=cohort.cohort_id,
                engine="cnv_rna",
                engine_version="1",
                input_materializations=seed_cnv_rna_inputs(session),
            ),
            "immutable-findings",
        )
        service.transition_analysis(str(analysis.analysis_id), "running")
        service.publish_findings(
            analysis,
            [
                FindingPayload(
                    snapshot_id="DS-TCGA-LUAD-test",
                    finding_type="cnv_expression_association",
gene="ENSG1",
                    cohort_size=2,
                    eligible_cases=1,
                    eligible_case_ids=("c1",),
                    eligible_sample_ids=("s1",),
                    n_effective=1,
                    effect_size=0.5,
                    confidence_interval=(0.1, 0.9),
                    p_value=0.01,
                    q_value=0.02,
                    missing_n=1,
                    missing_fraction=0.5,
                    analysis_version="cnv-rna-v1",
                    input_object_hashes=(f"sha256:{'b' * 64}",),
                    tested_gene_ids=("ENSG1",),
                    result_hash=f"sha256:{'e' * 64}",
                )
            ],
        )
    for statement in (
        "UPDATE findings SET payload = '{}'::jsonb",
        "DELETE FROM findings",
        "UPDATE cohorts SET definition = '{}'::jsonb",
        "DELETE FROM cohorts",
    ):
        with factory.begin() as session, pytest.raises(DBAPIError):
            session.execute(text(statement))


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
                        input_materializations=[seed_analysis_input(session)],
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
                input_materializations=[seed_analysis_input(session)],
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
        "UPDATE dataset_snapshots SET provenance = '{}'::jsonb",
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
        analysis_input = seed_analysis_input(session)
    request = {
        "snapshot_id": "DS-TCGA-LUAD-test",
        "cohort_id": cohort.cohort_id,
        "engine": "crossmodal",
        "engine_version": "1",
        "parameters": {},
        "expected_input_artifacts": [],
        "input_materializations": [analysis_input],
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
    if errors:
        raise errors[0]
    assert len(results) == 2 and results[0] == results[1]
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
        # ORM rows carry post-0006 columns; historical checks use raw SQL.
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
        assert (
            session.scalar(
                text("SELECT count(*) FROM dataset_snapshots WHERE snapshot_id = :id"),
                {"id": snapshot.snapshot_id},
            )
            == 1
        )
    command.upgrade(config, "head")
    with factory() as session:
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == "0007"
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


@pytest.mark.parametrize("publish_cas", [False, True])
def test_existing_pr7_snapshot_paths(factory, gdc_fixture, tmp_path, publish_cas):
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

        async def status(self):
            return {"version": "1", "data_release": "fixture", "status": "OK"}

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
        resources.register_snapshot(
            snapshot,
            _snapshot_artifacts(
                settings.snapshot_root, snapshot, settings if publish_cas else None
            ),
        )
        if publish_cas:
            # A consumer with no shared snapshot directory must resolve from CAS alone.
            settings = settings.model_copy(update={"snapshot_root": tmp_path / "not-mounted"})
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
