import json

import httpx
import pytest

from packages.gdc.client import GDCClient, GDCResponseError


@pytest.mark.asyncio
async def test_clinical_size_cap_before_json_decoding():
    from packages.gdc.client import GDCResponseTooLarge
    from packages.gdc.parsers import MAX_CLINICAL_BYTES

    async with httpx.AsyncClient(
        base_url="https://api.gdc.cancer.gov",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                content=b"{}",
                headers={
                    "content-length": str(MAX_CLINICAL_BYTES + 1),
                },
            )
        ),
    ) as http:
        client = GDCClient("https://api.gdc.cancer.gov", client=http)
        with pytest.raises(GDCResponseTooLarge):
            _ = [page async for page in client.clinical_pages(("c",))]


@pytest.mark.asyncio
async def test_clinical_pages_are_frozen_membership_bounded():
    calls = []

    def respond(request):
        calls.append(request)
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

    async with httpx.AsyncClient(
        base_url="https://api.gdc.cancer.gov", transport=httpx.MockTransport(respond)
    ) as http:
        client = GDCClient("https://api.gdc.cancer.gov", client=http)
        pages = [page async for page in client.clinical_pages(tuple(f"c{i}" for i in range(201)))]
    assert len(calls) == len(pages) == 3
    assert all(int(call.url.params["size"]) <= 100 for call in calls)
    assert len(json.loads(pages[-1][0])["data"]["hits"]) == 1
    assert pages[0][1]["endpoint"] == "https://api.gdc.cancer.gov/cases"


@pytest.mark.parametrize(
    "hits,total",
    [([{"case_id": "unrequested"}], 1), ([], 1), ([{"case_id": "c"}, {"case_id": "c"}], 2)],
)
@pytest.mark.asyncio
async def test_clinical_acquisition_rejects_inconsistent_identity(hits, total):
    async with httpx.AsyncClient(
        base_url="https://api.gdc.cancer.gov",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "data": {
                        "hits": hits,
                        "pagination": {"total": total},
                    }
                },
            )
        ),
    ) as http:
        client = GDCClient("https://api.gdc.cancer.gov", client=http)
        with pytest.raises(GDCResponseError):
            _ = [page async for page in client.clinical_pages(("c",))]
