import json

import pytest
import respx
from httpx import Response

from packages.gdc.client import GDCClient


@pytest.mark.asyncio
@respx.mock
async def test_file_query_enforces_open_access() -> None:
    route = respx.get("https://api.gdc.cancer.gov/files").mock(
        return_value=Response(200, json={"data": {"hits": []}})
    )
    async with GDCClient("https://api.gdc.cancer.gov") as client:
        await client.get_open_files("TCGA-LUAD")

    request = route.calls.last.request
    filters = json.loads(request.url.params["filters"])
    assert {"op": "=", "content": {"field": "files.access", "value": "open"}} in filters[
        "content"
    ]

