from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NoulQuestion(_StrictModel):
    type: Literal["noul"] = "noul"
    instructions: JsonValue


class ChoiceQuestion(_StrictModel):
    type: Literal["choice"] = "choice"
    instructions: JsonValue
    criteria: dict[str, JsonValue]

    @model_validator(mode="after")
    def require_choices(self) -> "ChoiceQuestion":
        if len(self.criteria) < 2:
            raise ValueError("a choice question requires at least two criteria")
        return self


class ScoreQuestion(_StrictModel):
    type: Literal["score"] = "score"
    instructions: JsonValue
    criteria: list[JsonValue] | dict[str, JsonValue]

    @model_validator(mode="after")
    def require_levels(self) -> "ScoreQuestion":
        if len(self.criteria) < 2:
            raise ValueError("a score question requires at least two criteria")
        return self


Question = Annotated[NoulQuestion | ChoiceQuestion | ScoreQuestion, Field(discriminator="type")]


class JevEvaluationRequest(_StrictModel):
    state: JsonValue
    questions: dict[str, Question] = Field(min_length=1)


class NoulAnswer(_StrictModel):
    type: Literal["noul"]
    noul: float = Field(ge=0, le=1)


class ChoiceAnswer(_StrictModel):
    type: Literal["choice"]
    choice: str
    probabilities: dict[str, float]
    confidence: float = Field(ge=0, le=1)


class ScoreAnswer(_StrictModel):
    type: Literal["score"]
    score: float
    probabilities: dict[str, float]
    confidence: float = Field(ge=0, le=1)
    legend: dict[str, Any] | None = None


Answer = Annotated[NoulAnswer | ChoiceAnswer | ScoreAnswer, Field(discriminator="type")]


class JevUsage(_StrictModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class JevEvaluationResponse(_StrictModel):
    model: str
    answers: dict[str, Answer]
    usage: JevUsage | None = None
    request_id: str | None = None


class EvidenceJudgmentRequest(_StrictModel):
    hypothesis: str = Field(min_length=1)
    evidence: JsonValue
    prediction: str | None = None


class EvidenceJudgment(_StrictModel):
    relation: Literal["SUPPORT", "CONTRADICT", "UNRESOLVED"]
    probabilities: dict[str, float]
    confidence: float = Field(ge=0, le=1)
    model: str
    label: Literal["Jev evidence-classification probability"] = (
        "Jev evidence-classification probability"
    )
