from pathlib import Path

import pytest

from packages.schemas.snapshot import LogicalSnapshotRequest
from packages.storage.snapshots import FileSnapshotRepository
from workers.ingest.snapshot import LogicalSnapshotService


class StubGDCClient:
    base_url = "https://api.gdc.cancer.gov"

    def __init__(self, access: str = "open"):
        self.access = access

    async def get_open_files(self, project_id: str) -> dict:
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
    request = LogicalSnapshotRequest(project_id="TCGA-LUAD", gdc_release="42")

    first = await service.create(request)
    second = await service.create(request)

    assert first.snapshot_hash == second.snapshot_hash
    assert first.snapshot_id == second.snapshot_id
    assert [item.file_id for item in first.objects] == ["f-1", "f-2"]
    assert (tmp_path / "TCGA-LUAD" / first.snapshot_id / "snapshot.json").is_file()


@pytest.mark.asyncio
async def test_snapshot_fails_closed_on_controlled_file(tmp_path: Path) -> None:
    service = LogicalSnapshotService(
        client=StubGDCClient(access="controlled"), repository=FileSnapshotRepository(tmp_path)
    )

    with pytest.raises(ValueError, match="controlled file"):
        await service.create(LogicalSnapshotRequest(project_id="TCGA-LUAD"))
