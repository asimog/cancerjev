"""CJ-R00 artifact execution path: frozen inputs, fenced publication, convergence."""

import os
import shutil
import uuid
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from sqlalchemy import create_engine, func, select, text

from packages.database.jobs import ClaimedJob, claim, succeed
from packages.database.models import Analysis, Job
from packages.database.models import Finding as FindingRow
from packages.provenance.hashing import canonical_hash
from packages.resources.execution import (
    AnalysisExecutionService,
    ExecutionFailure,
    IntegrityFailure,
    UnsupportedEngine,
)
from packages.resources.service import DurableResourceService
from packages.schemas.identity import (
    AliquotRecord,
    CaseRecord,
    FileSampleLink,
    SampleRecord,
)
from packages.schemas.resources import AnalysisCreate, ArtifactRegistration, CohortCreate
from packages.schemas.snapshot import SnapshotObject, SnapshotRecord
from packages.storage.config import StorageSettings
from packages.storage.objects import FileObjectStore, object_key
from packages.storage.parquet import write_records

DATABASE_URL = os.getenv("CANCERJEV_DATABASE_URL")
pytestmark = [
    pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL URL is not configured"),
    pytest.mark.postgres,
    pytest.mark.integration,
]

CASES = tuple(f"c{i}" for i in range(1, 7))
SAMPLES = {case: f"s{case[1:]}" for case in CASES}
GENE = "ENSG1"


@pytest.fixture
def factory(migrated_database):
    from packages.database.session import session_factory

    return session_factory(DATABASE_URL)


@pytest.fixture(autouse=True)
def settings(migrated_database, tmp_path, monkeypatch) -> StorageSettings:
    monkeypatch.setenv("CANCERJEV_OBJECT_BACKEND", "filesystem")
    monkeypatch.setenv("CANCERJEV_OBJECT_ROOT", str(tmp_path / "objects"))
    monkeypatch.setenv("CANCERJEV_SNAPSHOT_ROOT", str(tmp_path / "snapshots"))
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE idempotency_records, job_attempts, analyses, jobs, audit_events, "
                "findings, cohorts, snapshot_artifacts, snapshot_files, aliquots, samples, "
                "cases, dataset_snapshots, materializations, materialization_sources, "
                "dataset_objects, projects CASCADE"
            )
        )
    engine.dispose()
    return StorageSettings()


def seed_snapshot_graph(factory, settings: StorageSettings):
    store = FileObjectStore(settings.object_root)
    snapshot = SnapshotRecord(
        snapshot_id="DS-TCGA-LUAD-exec",
        snapshot_hash=canonical_hash({"exec": True}),
        project_id="TCGA-LUAD",
        source_api="https://api.gdc.cancer.gov",
        gdc_release="fixture",
        query={"access": "open"},
        transformation_version="logical-v1",
        case_ids=CASES,
        sample_ids=tuple(SAMPLES.values()),
        objects=(
            SnapshotObject(
                file_id="f-1", file_name="x.tsv", file_size=1, md5sum="a" * 32, access="open"
            ),
        ),
    )
    registrations = []
    for role, records, model in (
        ("cases", [CaseRecord(case_id=c, project_id="TCGA-LUAD") for c in CASES], CaseRecord),
        (
            "samples",
            [SampleRecord(sample_id=SAMPLES[c], case_id=c) for c in CASES],
            SampleRecord,
        ),
        ("aliquots", [], AliquotRecord),
        (
            "identity_links",
            [FileSampleLink(file_id="f-1", case_id=c, sample_id=SAMPLES[c]) for c in CASES],
            FileSampleLink,
        ),
    ):
        path = settings.object_root / f"{role}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_records(records, path, model=model)
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
        service = DurableResourceService(session)
        service.save_project("TCGA-LUAD")
        service.register_snapshot(snapshot, registrations)
    return snapshot, store


def register_modality(factory, settings, store, snapshot_id, modality, rows):
    """Register a materialization whose output parquet really exists in the store."""
    value_column = "cnv_value" if modality == "cnv" else "value"
    table = pa.table(
        {
            "case_id": [row[0] for row in rows],
            "sample_id": [row[1] for row in rows],
            "gene_id": [row[2] for row in rows],
            value_column: [row[3] for row in rows],
        }
    )
    path = settings.object_root / f"{modality}.parquet"
    pq.write_table(table, path)
    output_digest = store.put_file(path)
    diagnostics = f'{{"rows": {len(rows)}}}'.encode()
    diagnostics_digest = store.put(diagnostics)
    with factory.begin() as session:
        service = DurableResourceService(session)
        source = service.register_source(
            snapshot_id=snapshot_id,
            artifact=ArtifactRegistration(
                sha256="sha256:" + modality[0] * 64,
                size=1,
                media_type="application/octet-stream",
                logical_role="test_source",
                storage_backend="filesystem",
                storage_key="sha256/" + modality[0] * 2 + "/" + modality[0] * 64,
            ),
            source_file_id="f-1",
            source_metadata={"kind": "synthetic-test"},
        )
        materialization_id = canonical_hash(
            {"snapshot": snapshot_id, "modality": modality, "engine": "test"}
        )
        service.register_materialization(
            metadata=dict(
                materialization_id=materialization_id,
                snapshot_id=snapshot_id,
                source_id=source.source_id,
                output_sha256=output_digest,
                diagnostics_sha256=diagnostics_digest,
                modality=modality,
                measurement_type="tpm_unstranded" if modality == "expression" else "",
                parser_name="test-fixture",
                parser_version="1",
                schema_version="2",
                normalization_version="1",
                selection_version="1",
                logical_sha256="sha256:" + "f" * 64,
                row_count=len(rows),
                diagnostics_summary={},
            ),
            output=ArtifactRegistration(
                sha256=output_digest,
                size=path.stat().st_size,
                media_type="application/vnd.apache.parquet",
                logical_role=f"canonical_{modality}",
                storage_backend="filesystem",
                storage_key=object_key(output_digest),
            ),
            diagnostics=ArtifactRegistration(
                sha256=diagnostics_digest,
                size=len(diagnostics),
                media_type="application/json",
                logical_role="materialization_diagnostics",
                storage_backend="filesystem",
                storage_key=object_key(diagnostics_digest),
            ),
        )
        return {
            "materialization_id": materialization_id,
            "modality": modality,
            "measurement_type": "tpm_unstranded" if modality == "expression" else "",
        }


def cnv_rows(cases):
    return [(case, SAMPLES[case], GENE, int(case[1:]) - 1) for case in cases]


def rna_rows(cases):
    return [(case, SAMPLES[case], GENE, 2 * (int(case[1:]) - 1) + 1) for case in cases]


def build_analysis(
    factory,
    settings,
    store,
    cohort_cases,
    *,
    rna_cases=None,
    materialization_cases=None,
    engine="cnv_rna",
):
    snapshot_id = "DS-TCGA-LUAD-exec"
    with factory.begin() as session:
        service = DurableResourceService(session)
        cohort = service.create_cohort(
            CohortCreate(
                snapshot_id=snapshot_id,
                definition={"sample_type": "Primary Tumor"},
                case_ids=list(cohort_cases),
                sample_ids=[SAMPLES[c] for c in cohort_cases],
                exclusion_reasons={},
                selection_policy_version="primary-v1",
            )
        )
    input_cases = materialization_cases or cohort_cases
    inputs = [
        register_modality(factory, settings, store, snapshot_id, "cnv", cnv_rows(input_cases)),
        register_modality(
            factory,
            settings,
            store,
            snapshot_id,
            "expression",
            rna_rows(rna_cases or input_cases),
        ),
    ]
    with factory.begin() as session:
        return DurableResourceService(session).create_analysis(
            AnalysisCreate(
                snapshot_id=snapshot_id,
                cohort_id=cohort.cohort_id,
                engine=engine,
                engine_version="1",
                input_materializations=inputs,
            ),
            "execution-key",
        )


def claim_analysis(factory, worker: str) -> ClaimedJob:
    with factory.begin() as session:
        claimed = claim(session, worker, ("run_analysis_from_artifacts",))
    assert claimed is not None
    return claimed


def expire_leases(factory) -> None:
    with factory.begin() as session:
        session.execute(
            text("UPDATE jobs SET lease_expires_at = now() - interval '1 second'")
        )


def test_artifact_path_end_to_end(factory, settings):
    _, store = seed_snapshot_graph(factory, settings)
    analysis = build_analysis(factory, settings, store, CASES)
    claimed = claim_analysis(factory, "worker-exec")
    assert claimed.payload == {"analysis_id": str(analysis.analysis_id)}

    result = AnalysisExecutionService.run_claimed(claimed)

    assert result["published"] == 1 and result["converged"] is False
    with factory.begin() as session:
        row = session.get(Analysis, analysis.analysis_id)
        assert row.state == "completed" and row.error is None
        finding = session.scalar(select(FindingRow))
        assert finding.analysis_id == analysis.analysis_id
        payload = finding.payload
        assert payload["eligible_case_ids"] == list(CASES)
        assert payload["n_effective"] == 6
        assert payload["missing_n"] == 0
        assert payload["effect_size"] > 0.999
        assert finding.result_hash == payload["result_hash"]
        # run_claimed publishes but does not succeed the job; the runtime does.
        assert session.get(Job, claimed.job_id).state == "claimed"


def test_duplicate_canonical_keys_fail_as_invalid_scientific_input(factory, settings):
    _, store = seed_snapshot_graph(factory, settings)
    snapshot_id = "DS-TCGA-LUAD-exec"
    with factory.begin() as session:
        service = DurableResourceService(session)
        cohort = service.create_cohort(
            CohortCreate(
                snapshot_id=snapshot_id,
                definition={"sample_type": "Primary Tumor"},
                case_ids=list(CASES),
                sample_ids=[SAMPLES[c] for c in CASES],
                exclusion_reasons={},
                selection_policy_version="primary-v1",
            )
        )
    duplicated = cnv_rows(CASES) + cnv_rows(CASES)[:1]
    inputs = [
        register_modality(factory, settings, store, snapshot_id, "cnv", duplicated),
        register_modality(factory, settings, store, snapshot_id, "expression", rna_rows(CASES)),
    ]
    with factory.begin() as session:
        analysis = DurableResourceService(session).create_analysis(
            AnalysisCreate(
                snapshot_id=snapshot_id,
                cohort_id=cohort.cohort_id,
                engine="cnv_rna",
                engine_version="1",
                input_materializations=inputs,
            ),
            "duplicate-input-key",
        )
    claimed = claim_analysis(factory, "worker-exec")
    with pytest.raises(ExecutionFailure) as excinfo:
        AnalysisExecutionService.run_claimed(claimed)
    assert excinfo.value.failure_reason == "INVALID_SCIENTIFIC_INPUT"
    with factory() as session:
        row = session.get(Analysis, analysis.analysis_id)
        assert row.state == "running" and row.error is None


def test_cohort_membership_filters_rows_and_discloses_missingness(factory, settings):
    _, store = seed_snapshot_graph(factory, settings)
    # Five cohort members; one of them has no expression evidence.
    analysis = build_analysis(factory, settings, store, CASES[:5], rna_cases=CASES[:4])
    claimed = claim_analysis(factory, "worker-exec")
    result = AnalysisExecutionService.run_claimed(claimed)
    assert result["published"] == 1
    with factory() as session:
        finding = session.scalar(select(FindingRow))
        payload = finding.payload
        assert payload["eligible_case_ids"] == list(CASES[:4])
        assert payload["cohort_size"] == 5
        assert payload["missing_n"] == 1
        assert payload["missing_fraction"] == 0.2
        assert analysis.analysis_id == finding.analysis_id


def test_out_of_cohort_artifact_rows_cannot_become_finding_evidence(factory, settings):
    _, store = seed_snapshot_graph(factory, settings)
    build_analysis(
        factory,
        settings,
        store,
        CASES[:4],
        materialization_cases=CASES,
    )
    claimed = claim_analysis(factory, "worker-exec")
    assert AnalysisExecutionService.run_claimed(claimed)["published"] == 1
    with factory() as session:
        payload = session.scalar(select(FindingRow)).payload
        assert payload["cohort_size"] == 4
        assert payload["eligible_case_ids"] == list(CASES[:4])
        assert payload["eligible_sample_ids"] == [SAMPLES[c] for c in CASES[:4]]
        assert payload["n_effective"] == 4


def test_unsupported_engine_fails_deterministically(factory, settings):
    _, store = seed_snapshot_graph(factory, settings)
    analysis = build_analysis(factory, settings, store, CASES, engine="no_such_engine")
    claimed = claim_analysis(factory, "worker-exec")
    with pytest.raises(UnsupportedEngine) as excinfo:
        AnalysisExecutionService.run_claimed(claimed)
    assert excinfo.value.failure_reason == "UNSUPPORTED_ENGINE_OR_VERSION"
    with factory.begin() as session:
        assert session.get(Analysis, analysis.analysis_id).state == "running"


def test_missing_artifact_bytes_fail_closed(factory, settings, tmp_path: Path):
    _, store = seed_snapshot_graph(factory, settings)
    analysis = build_analysis(factory, settings, store, CASES)
    objects = list((tmp_path / "objects" / "sha256").rglob("*"))
    assert objects  # the store really held the artifact bytes before deletion
    shutil.rmtree(tmp_path / "objects")
    claimed = claim_analysis(factory, "worker-exec")
    with pytest.raises(IntegrityFailure):
        AnalysisExecutionService.run_claimed(claimed)
    with factory.begin() as session:
        assert session.get(Analysis, analysis.analysis_id).state == "running"


def test_stale_attempt_converges_after_publication(factory, settings):
    _, store = seed_snapshot_graph(factory, settings)
    analysis = build_analysis(factory, settings, store, CASES)
    claimed = claim_analysis(factory, "worker-exec")
    first = AnalysisExecutionService.run_claimed(claimed)
    assert first["converged"] is False

    # A stale worker re-runs the same claim after publication completed.
    result = AnalysisExecutionService.run_claimed(claimed)
    assert result["converged"] is True
    assert result["finding_ids"] == first["finding_ids"]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(FindingRow)) == 1
        assert session.get(Analysis, analysis.analysis_id).state == "completed"


def test_duplicate_execution_publishes_exactly_once(factory, settings):
    from packages.database.jobs import start

    _, store = seed_snapshot_graph(factory, settings)
    analysis = build_analysis(factory, settings, store, CASES)
    first = claim_analysis(factory, "worker-a")
    expire_leases(factory)
    second = claim_analysis(factory, "worker-b")
    assert second.attempt_token != first.attempt_token

    with factory.begin() as session:
        start(session, second.job_id, "worker-b", second.attempt_token)
    result_b = AnalysisExecutionService.run_claimed(second)
    with factory.begin() as session:
        succeed(
            session,
            second.job_id,
            "worker-b",
            second.attempt_token,
            {"analysis_id": result_b["analysis_id"]},
        )
    # The stale first attempt converges instead of duplicating publication.
    result_a = AnalysisExecutionService.run_claimed(first)
    assert result_a["converged"] is True
    assert result_a["finding_ids"] == result_b["finding_ids"]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(FindingRow)) == 1
        assert session.get(Analysis, analysis.analysis_id).state == "completed"


def test_payload_without_analysis_reference_fails(factory, settings):
    claimed = ClaimedJob(uuid.uuid4(), "run_analysis_from_artifacts", {}, "w", "t" * 64)
    with pytest.raises(ExecutionFailure, match="analysis_id"):
        AnalysisExecutionService.run_claimed(claimed)


def test_terminal_job_failure_marks_analysis_failed(factory, settings):
    from workers.statistics.__main__ import _fail_analysis

    _, store = seed_snapshot_graph(factory, settings)
    analysis = build_analysis(factory, settings, store, CASES)
    with factory.begin() as session:
        claimed = claim(session, "worker-exec", ("run_analysis_from_artifacts",))
        from packages.database.jobs import fail as fail_job

        state = fail_job(
            session,
            claimed.job_id,
            "worker-exec",
            claimed.attempt_token,
            "unsupported engine",
            False,
            "UNSUPPORTED_ENGINE_OR_VERSION",
        )
    assert state == "failed"
    _fail_analysis(str(claimed.job_id), dict(claimed.payload), "UNSUPPORTED_ENGINE_OR_VERSION")
    with factory() as session:
        row = session.get(Analysis, analysis.analysis_id)
        assert row.state == "failed" and "UNSUPPORTED_ENGINE_OR_VERSION" in row.error


def test_invalid_parquet_schema_rejected(factory, settings):
    _, store = seed_snapshot_graph(factory, settings)
    snapshot_id = "DS-TCGA-LUAD-exec"
    # An output parquet without the engine's required identity columns.
    path = settings.object_root / "bad.parquet"
    pq.write_table(pa.table({"case_id": ["c1"], "cnv_value": [1.0]}), path)
    digest = store.put_file(path)
    with factory.begin() as session:
        service = DurableResourceService(session)
        source = service.register_source(
            snapshot_id=snapshot_id,
            artifact=ArtifactRegistration(
                sha256="sha256:" + "d" * 64,
                size=1,
                media_type="application/octet-stream",
                logical_role="test_source",
                storage_backend="filesystem",
                storage_key="sha256/dd/" + "d" * 64,
            ),
            source_file_id="f-1",
            source_metadata={"kind": "synthetic-test"},
        )
        materialization_id = canonical_hash({"snapshot": snapshot_id, "modality": "cnv", "bad": 1})
        service.register_materialization(
            metadata=dict(
                materialization_id=materialization_id,
                snapshot_id=snapshot_id,
                source_id=source.source_id,
                output_sha256=digest,
                diagnostics_sha256="sha256:" + "b" * 64,
                modality="cnv",
                measurement_type="",
                parser_name="test-fixture",
                parser_version="1",
                schema_version="2",
                normalization_version="1",
                selection_version="1",
                logical_sha256="sha256:" + "f" * 64,
                row_count=1,
                diagnostics_summary={},
            ),
            output=ArtifactRegistration(
                sha256=digest,
                size=path.stat().st_size,
                media_type="application/vnd.apache.parquet",
                logical_role="canonical_cnv",
                storage_backend="filesystem",
                storage_key=object_key(digest),
            ),
            diagnostics=ArtifactRegistration(
                sha256="sha256:" + "b" * 64,
                size=1,
                media_type="application/json",
                logical_role="materialization_diagnostics",
                storage_backend="filesystem",
                storage_key="sha256/bb/" + "b" * 64,
            ),
        )
        cohort = service.create_cohort(
            CohortCreate(
                snapshot_id=snapshot_id,
                definition={},
                case_ids=list(CASES),
                sample_ids=[SAMPLES[c] for c in CASES],
                exclusion_reasons={},
                selection_policy_version="primary-v1",
            )
        )
        rna_input = register_modality(
            factory, settings, store, snapshot_id, "expression", rna_rows(CASES)
        )
        analysis = service.create_analysis(
            AnalysisCreate(
                snapshot_id=snapshot_id,
                cohort_id=cohort.cohort_id,
                engine="cnv_rna",
                engine_version="1",
                input_materializations=[
                    {
                        "materialization_id": materialization_id,
                        "modality": "cnv",
                        "measurement_type": "",
                    },
                    rna_input,
                ],
            ),
            "bad-schema-key",
        )
    claimed = claim_analysis(factory, "worker-exec")
    with pytest.raises(ExecutionFailure, match="required columns"):
        AnalysisExecutionService.run_claimed(claimed)
    with factory.begin() as session:
        assert session.get(Analysis, analysis.analysis_id).state == "running"
