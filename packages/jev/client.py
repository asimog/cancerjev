from collections.abc import Mapping
from typing import Any, Self

import httpx

from packages.jev.schemas import JevEvaluationRequest, JevEvaluationResponse


class JevClient:
    """Async adapter for TypeSafe's System One evaluation endpoint."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        model: str = "jev-latest",
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
        if settings.jev_api_key is None:
            raise ValueError("CANCERJEV_JEV_API_KEY is not configured")
        return cls(
            str(settings.jev_base_url),
            settings.jev_api_key.get_secret_value(),
            model=settings.jev_model,
            timeout=settings.ai_timeout_seconds,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def evaluate(self, request: JevEvaluationRequest) -> JevEvaluationResponse:
        payload = request.model_dump(mode="json")
        payload["model"] = self.model
        response = await self._http.post("/v1/systemone", json=payload)
        response.raise_for_status()
        result = JevEvaluationResponse.model_validate(response.json())
        if result.answers.keys() != request.questions.keys():
            raise ValueError("Jev response question IDs do not match the request")
        return result

    async def evaluate_raw(
        self, *, state: Any, questions: Mapping[str, Mapping[str, Any]]
    ) -> JevEvaluationResponse:
        return await self.evaluate(
            JevEvaluationRequest.model_validate({"state": state, "questions": questions})
        )
