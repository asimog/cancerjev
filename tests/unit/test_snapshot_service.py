import hashlib
import json
from pathlib import Path

import pytest

from packages.schemas.snapshot import LogicalSnapshotRequest, SnapshotRecord
from packages.storage.parquet import query
from packages.storage.snapshots import (
    REQUIRED_ARTIFACTS,
    FileSnapshotRepository,
    SnapshotConflictError,
)
from workers.ingest.snapshot import LogicalSnapshotService, map_snapshot_object


class StubGDCClient:
    base_url = "https://api.gdc.cancer.gov"

    async def status(self):
        return {"version": "1", "data_release": "42", "status": "OK"}

    def __init__(self, access: str = "open"):
        self.access = access

    async def get_open_files(self, project_id: str, **_: object) -> dict:
        assert project_id == "TCGA-LUAD"
        return {
            "data": {
                "hits": [
                    {
                        "file_id": "f-2",
                        "file_name": "two.tsv",
                        "file_size": 20,
                        "md5sum": "b" * 32,
                        "access": self.access,
                    },
                    {
                        "file_id": "f-1",
                        "file_name": "one.tsv",
                        "file_size": 10,
                        "md5sum": "a" * 32,
                        "access": "open",
                    },
                ]
            }
        }


@pytest.mark.asyncio
async def test_snapshot_is_deterministic_and_persisted(tmp_path: Path) -> None:
    service = LogicalSnapshotService(
        client=StubGDCClient(), repository=FileSnapshotRepository(tmp_path)
    )
    request = LogicalSnapshotRequest(project_id="TCGA-LUAD")

    first = await service.create(request)
    second = await service.create(request)

    assert first.snapshot_hash == second.snapshot_hash
    assert first.snapshot_id == second.snapshot_id
    assert first.created_at == second.created_at
    assert [item.file_id for item in first.objects] == ["f-1", "f-2"]
    assert (tmp_path / "TCGA-LUAD" / first.snapshot_id / "snapshot.json").is_file()
    root = tmp_path / "TCGA-LUAD" / first.snapshot_id
    assert {path.name for path in root.iterdir()} == REQUIRED_ARTIFACTS
    aliquots = query(root / "aliquots.parquet")
    assert aliquots.height == 0
    assert aliquots.columns == ["aliquot_id", "sample_id", "submitter_id"]


@pytest.mark.asyncio
async def test_snapshot_fails_closed_on_controlled_file(tmp_path: Path) -> None:
    service = LogicalSnapshotService(
        client=StubGDCClient(access="controlled"), repository=FileSnapshotRepository(tmp_path)
    )

    with pytest.raises(ValueError, match="controlled file"):
        await service.create(LogicalSnapshotRequest(project_id="TCGA-LUAD"))


def test_raw_gdc_file_hit_is_explicitly_projected() -> None:
    hit = {
        "file_id": "0da7c91b-1f17-4e0c-91de-8d79b118ce53",
        "file_name": "augmented_star_gene_counts.tsv",
        "file_size": 918273,
        "md5sum": "0123456789abcdef0123456789abcdef",
        "access": "open",
        "data_type": "Gene Expression Quantification",
        "data_format": "TSV",
        "data_category": "Transcriptome Profiling",
        "experimental_strategy": "RNA-Seq",
        "analysis": {"workflow_type": "STAR - Counts"},
        "cases": [{"case_id": "4ec0", "samples": [{"sample_id": "ad31"}]}],
    }
    canonical = map_snapshot_object(hit)
    assert canonical.file_id == hit["file_id"]
    assert "cases" not in canonical.model_dump()


class RelationshipClient:
    base_url = "https://api.gdc.cancer.gov"

    async def status(self):
        return {"version": "1", "data_release": "42", "status": "OK"}

    def __init__(self, swapped: bool = False):
        self.swapped = swapped

    async def get_open_files(self, project_id: str, **_: object) -> dict:
        sample_ids = ("s-2", "s-1") if self.swapped else ("s-1", "s-2")
        hits = []
        for index, sample_id in enumerate(sample_ids, 1):
            hits.append(
                {
                    "file_id": f"f-{index}",
                    "file_name": f"{index}.tsv",
                    "file_size": index,
                    "md5sum": str(index) * 32,
                    "access": "open",
                    "data_type": "Gene Expression Quantification",
                    "cases": [
                        {
                            "case_id": "c-1",
                            "project": {"project_id": project_id},
                            "samples": [{"sample_id": sample_id, "sample_type": "Primary Tumor"}],
                        }
                    ],
                }
            )
        return {"data": {"hits": hits}}


@pytest.mark.asyncio
async def test_relationship_and_version_changes_affect_identity(tmp_path: Path) -> None:
    request = LogicalSnapshotRequest(project_id="TCGA-LUAD")
    normal = await LogicalSnapshotService(
        client=RelationshipClient(), repository=FileSnapshotRepository(tmp_path / "normal")
    ).create(request)
    swapped = await LogicalSnapshotService(
        client=RelationshipClient(swapped=True),
        repository=FileSnapshotRepository(tmp_path / "swap"),
    ).create(request)
    changed_fields = await LogicalSnapshotService(
        client=RelationshipClient(), repository=FileSnapshotRepository(tmp_path / "fields")
    ).create(request.model_copy(update={"requested_fields": ("file_id", "created_datetime")}))
    changed_policy = await LogicalSnapshotService(
        client=RelationshipClient(), repository=FileSnapshotRepository(tmp_path / "policy")
    ).create(request.model_copy(update={"selection_policy_version": "open-project-files-v2"}))
    assert (
        len(
            {
                normal.snapshot_hash,
                swapped.snapshot_hash,
                changed_fields.snapshot_hash,
                changed_policy.snapshot_hash,
            }
        )
        == 4
    )
    assert normal.case_ids == swapped.case_ids
    assert normal.sample_ids == swapped.sample_ids


@pytest.mark.asyncio
async def test_failed_publication_leaves_no_final_snapshot(tmp_path: Path, monkeypatch) -> None:
    def fail_manifest(_files):
        raise RuntimeError("injected failure")

    monkeypatch.setattr("workers.ingest.snapshot.generate_manifest", fail_manifest)
    service = LogicalSnapshotService(
        client=StubGDCClient(), repository=FileSnapshotRepository(tmp_path)
    )
    with pytest.raises(RuntimeError, match="injected"):
        await service.create(LogicalSnapshotRequest(project_id="TCGA-LUAD"))
    project_root = tmp_path / "TCGA-LUAD"
    assert not project_root.exists() or list(project_root.iterdir()) == []


@pytest.mark.asyncio
async def test_corrupt_existing_snapshot_is_rejected(tmp_path: Path) -> None:
    service = LogicalSnapshotService(
        client=StubGDCClient(), repository=FileSnapshotRepository(tmp_path)
    )
    snapshot = await service.create(LogicalSnapshotRequest(project_id="TCGA-LUAD"))
    marker = tmp_path / "TCGA-LUAD" / snapshot.snapshot_id / "COMPLETE.json"
    marker.write_text('{"snapshot_hash":"sha256:wrong"}', encoding="utf-8")
    with pytest.raises(SnapshotConflictError, match="conflicts"):
        await service.create(LogicalSnapshotRequest(project_id="TCGA-LUAD"))


def hit(file_id: str, case_submitter: str = "case-A", sample_type: str = "Primary Tumor") -> dict:
    # Deterministic fixture checksum; not an upstream GDC claim.
    return {
        "file_id": file_id,
        "file_name": f"{file_id}.tsv",
        "file_size": 10,
        "md5sum": hashlib.sha256(file_id.encode()).hexdigest()[:32],
        "access": "open",
        "cases": [
            {
                "case_id": "c-1",
                "submitter_id": case_submitter,
                "project": {"project_id": "TCGA-LUAD"},
                "samples": [{"sample_id": "s-1", "sample_type": sample_type}],
            }
        ],
    }


class ListingClient:
    base_url = "https://api.gdc.cancer.gov"

    def __init__(self, hits: list[dict]):
        self.hits = hits

    async def status(self):
        return {"version": "1", "data_release": "42", "status": "OK"}

    async def get_open_files(self, project_id: str, **_: object) -> dict:
        return {"data": {"hits": self.hits}}


@pytest.mark.asyncio
async def test_conflicting_duplicate_biological_records_fail_closed(tmp_path: Path) -> None:
    conflicting = ListingClient([hit("f-1"), hit("f-2", case_submitter="case-B")])
    with pytest.raises(ValueError, match="conflicting_case_identity"):
        await LogicalSnapshotService(
            client=conflicting, repository=FileSnapshotRepository(tmp_path)
        ).create(LogicalSnapshotRequest(project_id="TCGA-LUAD"))


@pytest.mark.asyncio
async def test_exact_duplicate_records_collapse(tmp_path: Path) -> None:
    duplicate = ListingClient([hit("f-1"), hit("f-2")])
    snapshot = await LogicalSnapshotService(
        client=duplicate, repository=FileSnapshotRepository(tmp_path)
    ).create(LogicalSnapshotRequest(project_id="TCGA-LUAD"))
    root = tmp_path / "TCGA-LUAD" / snapshot.snapshot_id
    cases = query(root / "cases.parquet")
    assert cases.height == 1 and cases["submitter_id"][0] == "case-A"
    links = query(root / "file_sample_links.parquet")
    assert links.height == 2


@pytest.mark.asyncio
async def test_v2_identity_is_invariant_to_hit_ordering(tmp_path: Path) -> None:
    forward = await LogicalSnapshotService(
        client=ListingClient([hit("f-1"), hit("f-2")]),
        repository=FileSnapshotRepository(tmp_path / "forward"),
    ).create(LogicalSnapshotRequest(project_id="TCGA-LUAD"))
    reversed_ = await LogicalSnapshotService(
        client=ListingClient([hit("f-2"), hit("f-1")]),
        repository=FileSnapshotRepository(tmp_path / "reverse"),
    ).create(LogicalSnapshotRequest(project_id="TCGA-LUAD"))
    assert forward.snapshot_hash == reversed_.snapshot_hash
    assert forward.snapshot_id == reversed_.snapshot_id


@pytest.mark.asyncio
async def test_record_field_changes_change_the_v2_digest(tmp_path: Path) -> None:
    request = LogicalSnapshotRequest(project_id="TCGA-LUAD")
    base = await LogicalSnapshotService(
        client=ListingClient([hit("f-1")]),
        repository=FileSnapshotRepository(tmp_path / "base"),
    ).create(request)
    changed_submitter = await LogicalSnapshotService(
        client=ListingClient([hit("f-1", case_submitter="case-B")]),
        repository=FileSnapshotRepository(tmp_path / "submitter"),
    ).create(request)
    changed_sample_type = await LogicalSnapshotService(
        client=ListingClient([hit("f-1", sample_type="Solid Tissue Normal")]),
        repository=FileSnapshotRepository(tmp_path / "sample"),
    ).create(request)
    digests = {
        base.snapshot_hash,
        changed_submitter.snapshot_hash,
        changed_sample_type.snapshot_hash,
    }
    assert len(digests) == 3
    assert base.identity_version == 2


def test_legacy_v1_snapshot_record_remains_readable() -> None:
    legacy = {
        "snapshot_id": "DS-TCGA-LUAD-legacy",
        "snapshot_hash": "sha256:" + "0" * 64,
        "project_id": "TCGA-LUAD",
        "source_api": "https://api.gdc.cancer.gov",
        "gdc_release": "42",
        "query": {},
        "transformation_version": "logical-v1",
        "objects": [
            {
                "file_id": "f-1",
                "file_name": "one.tsv",
                "file_size": 10,
                "md5sum": "a" * 32,
                "access": "open",
            }
        ],
    }
    record = SnapshotRecord.model_validate_json(json.dumps(legacy))
    assert record.identity_version == 1
    assert record.case_ids == ()
