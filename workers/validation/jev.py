from packages.jev.client import JevClient
from packages.jev.schemas import (
    ChoiceAnswer,
    ChoiceQuestion,
    EvidenceJudgment,
    EvidenceJudgmentRequest,
    JevEvaluationRequest,
)


class JevEvidenceService:
    """Runs CancerJev's canonical, versioned evidence relationship question."""

    QUESTION_VERSION = "evidence-relation-v1"

    def __init__(self, client: JevClient):
        self.client = client

    async def judge(self, request: EvidenceJudgmentRequest) -> EvidenceJudgment:
        state = {
            "hypothesis": request.hypothesis,
            "evidence": request.evidence,
            "prediction": request.prediction,
        }
        evaluation = await self.client.evaluate(
            JevEvaluationRequest(
                state=state,
                questions={
                    "evidence_relation": ChoiceQuestion(
                        instructions={
                            "version": self.QUESTION_VERSION,
                            "question": (
                                "What relationship does the supplied evidence have to the "
                                "hypothesis? Judge only the evidence shown. Do not infer that "
                                "agreement proves the biological mechanism."
                            ),
                        },
                        criteria={
                            "SUPPORT": "The evidence supports the stated hypothesis.",
                            "CONTRADICT": "The evidence contradicts the stated hypothesis.",
                            "UNRESOLVED": (
                                "The evidence is insufficient, indirect, or does not distinguish "
                                "support from contradiction."
                            ),
                        },
                    )
                },
            )
        )
        answer = evaluation.answers["evidence_relation"]
        if not isinstance(answer, ChoiceAnswer):
            raise ValueError("Jev returned the wrong answer type for evidence_relation")
        return EvidenceJudgment(
            relation=answer.choice,
            probabilities=answer.probabilities,
            confidence=answer.confidence,
            model=evaluation.model,
        )
