import gzip
import json
from unittest.mock import patch

import httpx
import pytest
import respx

from apps.api.config import Settings
from packages.gdc.client import GDCClient, GDCError, GDCResponseError
from packages.gdc.manifest import generate_manifest
from packages.gdc.transfer import GDCTransfer
from packages.schemas.identity import FileRecord
from packages.schemas.snapshot import LogicalSnapshotRequest, SnapshotObject, SnapshotRecord
from packages.storage.snapshots import FileSnapshotRepository
from workers.ingest.snapshot import LogicalSnapshotService

BASE = "https://api.gdc.cancer.gov"
FILE_ID = "0052ae83-7ae5-470a-a125-5cd94a9fa9e9"
STATUS = {"version": 1, "data_release": "Data Release 46.0", "commit": "test"}


@respx.mock
async def test_compressed_official_responses_are_decoded_exactly_once():
    raw = json.dumps({"data": {"hits": [{"access": "open", "file_id": FILE_ID}]}}).encode()
    respx.get(BASE + "/files").respond(
        200, content=gzip.compress(raw), headers={"content-encoding": "gzip"}
    )
    async with GDCClient(BASE) as client:
        assert await client.endpoint("files") == [{"access": "open", "file_id": FILE_ID}]


def frozen_snapshot():
    return SnapshotRecord(
        snapshot_id="DS-test",
        snapshot_hash="sha256:" + "1" * 64,
        project_id="TCGA-LUAD",
        source_api=BASE,
        gdc_release="46",
        query={},
        transformation_version="1",
        objects=(
            SnapshotObject(
                file_id=FILE_ID, file_name="rna.tsv", file_size=10, md5sum="a" * 32, access="open"
            ),
        ),
    )


@pytest.mark.parametrize("access", ["controlled", None, "unknown", "Open", ""])
@respx.mock
async def test_files_fail_closed_for_every_non_open_response(access):
    hit = {"file_id": FILE_ID}
    if access is not None:
        hit["access"] = access
    respx.get(BASE + "/files").respond(200, json={"data": {"hits": [hit]}})
    async with GDCClient(BASE) as client:
        with pytest.raises(ValueError, match="explicit open"):
            await client.endpoint("files")


@pytest.mark.parametrize("entry", ["endpoint", "collect", "paginate"])
@respx.mock
async def test_caller_cannot_override_open_filter_or_omit_access(entry):
    route = respx.get(BASE + "/files").respond(200, json={"data": {"hits": []}})
    caller = {"op": "=", "content": {"field": "files.access", "value": "controlled"}}
    params = {"filters": json.dumps(caller), "fields": "file_id"}
    async with GDCClient(BASE) as client:
        if entry == "endpoint":
            await client.endpoint("files", params=params)
        elif entry == "collect":
            await client.collect("/files", params=params)
        else:
            assert [hit async for hit in client.paginate("/files", params=params)] == []
    query = route.calls.last.request.url.params
    assert json.loads(query["filters"]) == {
        "op": "and",
        "content": [
            {"op": "=", "content": {"field": "files.access", "value": "open"}},
            caller,
        ],
    }
    assert "access" in query["fields"].split(",")
    assert params["filters"] == json.dumps(caller)
    assert not {"authorization", "x-auth-token", "cookie"}.intersection(
        route.calls.last.request.headers
    )


@pytest.mark.parametrize(
    "host",
    [
        "http://api.gdc.cancer.gov",
        "https://api.gdc.cancer.gov.evil.test",
        "https://user:password@api.gdc.cancer.gov",
        "https://api.gdc.cancer.gov/other",
        "https://example.org",
        "https://api.gdc.cancer.gov?host=other",
    ],
)
def test_official_host_enforced_in_settings_and_transport(host):
    with pytest.raises(ValueError, match="official GDC"):
        GDCClient(host)
    with pytest.raises(ValueError, match="official GDC"):
        Settings(gdc_base_url=host)


@respx.mock
async def test_redirect_never_follows_another_host():
    respx.get(BASE + "/status").respond(302, headers={"location": "https://evil.test/status"})
    async with GDCClient(BASE) as client:
        with pytest.raises(GDCError, match="302"):
            await client.status()
    assert len(respx.calls) == 1


@pytest.mark.parametrize("header", ["X-Auth-Token", "Authorization", "Cookie"])
@respx.mock
async def test_injected_authentication_headers_are_rejected_before_network(header):
    async with httpx.AsyncClient(headers={header: "test-only"}) as http:
        client = GDCClient(BASE, client=http)
        with pytest.raises(ValueError, match="authentication"):
            await client.status()
    assert len(respx.calls) == 0


@respx.mock
async def test_injected_client_cannot_change_source_host():
    route = respx.get(BASE + "/status").respond(200, json=STATUS)
    async with httpx.AsyncClient(base_url="https://evil.test") as http:
        assert await GDCClient(BASE, client=http).status() == STATUS
    assert route.called


@respx.mock
async def test_manifest_requires_frozen_subset_and_unchanged_upstream_metadata():
    snapshot = frozen_snapshot()
    raw = generate_manifest([FileRecord(**snapshot.objects[0].model_dump())])
    route = respx.post(BASE + "/manifest").respond(200, content=raw)
    async with GDCClient(BASE) as client:
        with pytest.raises(ValueError, match="frozen snapshot"):
            await client.manifest([FILE_ID])
        for ids in (["arbitrary-uuid"], []):
            with pytest.raises(ValueError, match="subset"):
                await client.manifest(snapshot, ids)
        assert not route.called
        assert await client.manifest(snapshot, [FILE_ID]) == raw
        route.respond(200, content=raw.replace(b"released", b"validated"))
        assert await client.manifest(snapshot) == raw.replace(b"released", b"validated")
        route.respond(200, content=raw.replace(b"released", b"deleted"))
        with pytest.raises(ValueError, match="metadata differs"):
            await client.manifest(snapshot)
        route.respond(200, content=raw.replace(b"rna.tsv", b"changed.tsv"))
        with pytest.raises(ValueError, match="metadata differs"):
            await client.manifest(snapshot)


@respx.mock
async def test_documented_provenance_endpoints():
    status = respx.get(BASE + "/status").respond(200, json=STATUS)
    versions = respx.get(BASE + "/files/versions/" + FILE_ID).respond(200, json=[])
    history = respx.get(BASE + "/history/" + FILE_ID).respond(200, json=[])
    mapping = respx.get(BASE + "/files/_mapping").respond(200, json={"fields": ["access"]})
    async with GDCClient(BASE) as client:
        assert await client.status() == STATUS
        assert await client.file_versions([FILE_ID]) == []
        assert await client.history(FILE_ID) == []
        assert await client.mapping("files") == {"fields": ["access"]}
        with pytest.raises(ValueError):
            await client.endpoint("gene_expression")
    assert all(route.called for route in (status, versions, history, mapping))


@pytest.mark.parametrize("value", [{}, {"version": 1}, {"version": None, "data_release": "46"}])
@respx.mock
async def test_status_missing_provenance_fails_closed(value):
    respx.get(BASE + "/status").respond(200, json=value)
    async with GDCClient(BASE) as client:
        with pytest.raises(GDCResponseError):
            await client.status()


@respx.mock
async def test_snapshot_status_is_frozen_and_release_cannot_be_supplied(tmp_path):
    with pytest.raises(ValueError):
        LogicalSnapshotRequest(project_id="TCGA-LUAD", gdc_release="fabricated")
    status = respx.get(BASE + "/status").respond(200, json=STATUS)
    respx.get(BASE + "/files").respond(200, json={"data": {"hits": []}})
    async with GDCClient(BASE) as client:
        service = LogicalSnapshotService(client=client, repository=FileSnapshotRepository(tmp_path))
        snapshot = await service.create(LogicalSnapshotRequest(project_id="TCGA-LUAD"))
        assert snapshot.gdc_release == STATUS["data_release"]
        assert snapshot.upstream_provenance["status"] == STATUS
        assert len(status.calls) == 2
        status.side_effect = [
            httpx.Response(200, json=STATUS),
            httpx.Response(200, json=STATUS | {"data_release": "47"}),
        ]
        with pytest.raises(ValueError, match="status changed"):
            await service.create(LogicalSnapshotRequest(project_id="TCGA-LUAD"))


def test_transfer_capability_probe_is_argument_safe():
    with (
        patch("packages.gdc.transfer.shutil.which", return_value="/usr/bin/gdc-client"),
        patch("packages.gdc.transfer.subprocess.run") as run,
    ):
        run.return_value.returncode = 0
        run.return_value.stdout = "gdc-client 1.6.0"
        assert GDCTransfer().capability() == "gdc-client 1.6.0"
    assert run.call_args.args[0] == ["/usr/bin/gdc-client", "--version"]
