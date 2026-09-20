from typing import Any, Self

import httpx


class OpenRouterClient:
    """Generative LLM adapter, kept separate from the Jev decision client."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        model: str,
        timeout: float = 30,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "CancerJev/0.1 (research use only)",
            },
        )

    @classmethod
    def from_settings(cls, settings: Any) -> Self:
        if settings.llm_api_key is None:
            raise ValueError("CANCERJEV_LLM_API_KEY is not configured")
        return cls(
            str(settings.llm_base_url),
            settings.llm_api_key.get_secret_value(),
            model=settings.llm_model,
            timeout=settings.ai_timeout_seconds,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def chat(self, messages: list[dict[str, str]], **parameters: Any) -> dict[str, Any]:
        response = await self._http.post(
            "/chat/completions",
            json={"model": self.model, "messages": messages, **parameters},
        )
        response.raise_for_status()
        return response.json()
