import pytest
import respx
from httpx import Response

from packages.gdc.client import GDCClient, GDCResponseError


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
