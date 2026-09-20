import json

import httpx
import pytest

from packages.jev.client import JevClient
from packages.jev.schemas import EvidenceJudgmentRequest, JevEvaluationRequest
from workers.validation.jev import JevEvidenceService


def jev_transport(request: httpx.Request) -> httpx.Response:
    assert request.url == "https://jev.example/v1/systemone"
    assert request.headers["authorization"] == "Bearer jev-secret"
    payload = json.loads(request.content)
    assert payload["model"] == "jev-latest"
    assert payload["questions"]["evidence_relation"]["type"] == "choice"
    return httpx.Response(
        200,
        json={
            "model": "jev-1.13.0",
            "answers": {
                "evidence_relation": {
                    "type": "choice",
                    "choice": "SUPPORT",
                    "confidence": 0.82,
                    "probabilities": {
                        "SUPPORT": 0.88,
                        "CONTRADICT": 0.03,
                        "UNRESOLVED": 0.09,
                    },
                }
            },
            "usage": {"input_tokens": 42, "output_tokens": 7},
        },
    )


@pytest.mark.asyncio
async def test_canonical_evidence_judgment_uses_typed_jev_choice() -> None:
    async with JevClient(
        "https://jev.example",
        "jev-secret",
        transport=httpx.MockTransport(jev_transport),
    ) as client:
        result = await JevEvidenceService(client).judge(
            EvidenceJudgmentRequest(
                hypothesis="EGFR activation increases pathway activity",
                evidence={"effect": 1.4, "q_value": 0.002},
            )
        )

    assert result.relation == "SUPPORT"
    assert result.confidence == 0.82
    assert result.label == "Jev evidence-classification probability"


@pytest.mark.asyncio
async def test_jev_rejects_mismatched_question_ids() -> None:
    def mismatched(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "answers": {"other": {"type": "noul", "noul": 0.5}},
            },
        )

    async with JevClient(
        "https://jev.example", "secret", transport=httpx.MockTransport(mismatched)
    ) as client:
        with pytest.raises(ValueError, match="question IDs"):
            await client.evaluate(
                JevEvaluationRequest(
                    state="state",
                    questions={"expected": {"type": "noul", "instructions": "Is this supported?"}},
                )
            )
