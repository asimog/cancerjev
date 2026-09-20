import pytest
import respx
from httpx import AsyncByteStream, Response

from packages.gdc.client import GDCClient, GDCResponseError, GDCResponseTooLarge


class Chunked(AsyncByteStream):
    def __init__(self, *chunks: bytes):
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk


@pytest.mark.asyncio
@respx.mock
async def test_pagination_uses_confirmed_total() -> None:
    route = respx.get("https://api.gdc.cancer.gov/cases").mock(
        side_effect=[
            Response(200, json={"data": {"hits": [{"id": 1}], "pagination": {"total": 2}}}),
            Response(200, json={"data": {"hits": [{"id": 2}], "pagination": {"total": 2}}}),
        ]
    )
    async with GDCClient("https://api.gdc.cancer.gov", page_size=1) as client:
        assert await client.collect("/cases") == [{"id": 1}, {"id": 2}]
    assert len(route.calls) == 2


@pytest.mark.asyncio
@respx.mock
async def test_malformed_payload_fails_closed() -> None:
    respx.get("https://api.gdc.cancer.gov/cases").mock(return_value=Response(200, json={"oops": 1}))
    async with GDCClient("https://api.gdc.cancer.gov") as client:
        with pytest.raises(GDCResponseError):
            await client.collect("/cases")


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("limit", [1, 2, 3])
async def test_project_limit_stops_upstream_pagination(limit: int) -> None:
    route = respx.get("https://api.gdc.cancer.gov/projects").mock(
        side_effect=[
            Response(
                200,
                json={
                    "data": {
                        "hits": [{"project_id": "A"}, {"project_id": "B"}],
                        "pagination": {"total": 5},
                    }
                },
            ),
            Response(
                200,
                json={"data": {"hits": [{"project_id": "C"}], "pagination": {"total": 5}}},
            ),
        ]
    )
    async with GDCClient("https://api.gdc.cancer.gov", page_size=2) as client:
        result = await client.get_projects(size=limit)
    assert len(result["data"]["hits"]) == limit
    assert len(route.calls) == (1 if limit <= 2 else 2)
    assert route.calls[0].request.url.params["size"] == str(min(limit, 2))


@pytest.mark.asyncio
@respx.mock
async def test_final_partial_page_and_exact_limit() -> None:
    route = respx.get("https://api.gdc.cancer.gov/cases").mock(
        side_effect=[
            Response(200, json={"data": {"hits": [{"id": 1}, {"id": 2}]}}),
            Response(200, json={"data": {"hits": [{"id": 3}]}}),
        ]
    )
    async with GDCClient("https://api.gdc.cancer.gov", page_size=2) as client:
        assert await client.collect("/cases", limit=3) == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert len(route.calls) == 2


@pytest.mark.asyncio
@respx.mock
async def test_chunked_response_without_content_length_is_bounded_and_not_retried() -> None:
    route = respx.get("https://api.gdc.cancer.gov/cases").mock(
        return_value=Response(
            200,
            headers={"transfer-encoding": "chunked"},
            stream=Chunked(b'{"data":', b' {"hits": [', b"0" * 100),
        )
    )
    async with GDCClient(
        "https://api.gdc.cancer.gov", max_response_bytes=20, max_retries=4
    ) as client:
        with pytest.raises(GDCResponseTooLarge):
            await client.collect("/cases")
    assert len(route.calls) == 1


def test_project_limit_is_bounded() -> None:
    client = GDCClient("https://api.gdc.cancer.gov")
    with pytest.raises(ValueError, match="between 1 and 100"):
        import asyncio

        asyncio.run(client.get_projects(size=101))
    asyncio.run(client.aclose())
