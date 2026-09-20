import json

import httpx
import pytest

from packages.providers.openrouter import OpenRouterClient


@pytest.mark.asyncio
async def test_llm_client_uses_its_own_openrouter_endpoint_and_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://llm.example/api/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer llm-secret"
        payload = json.loads(request.content)
        assert payload["model"] == "research/model"
        assert payload["temperature"] == 0.2
        return httpx.Response(200, json={"choices": []})

    async with OpenRouterClient(
        "https://llm.example/api/v1",
        "llm-secret",
        model="research/model",
        transport=httpx.MockTransport(handler),
    ) as client:
        response = await client.chat(
            [{"role": "user", "content": "Propose a falsifier"}], temperature=0.2
        )

    assert response == {"choices": []}
