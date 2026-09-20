from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProvenanceModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceVersion(ProvenanceModel):
    source: str
    version: str | None
    api: str


class UpstreamRepositoryVersion(ProvenanceModel):
    repository: str
    commit: str
    license: str


class TransformationVersion(ProvenanceModel):
    name: str
    version: str


class AnalysisVersion(ProvenanceModel):
    name: str
    version: str
    parameters: dict


class SoftwareEnvironment(ProvenanceModel):
    python: str
    packages: dict[str, str]


class ObjectDigest(ProvenanceModel):
    algorithm: str
    value: str
    size: int


class ResultDigest(ProvenanceModel):
    analysis_id: str
    digest: ObjectDigest
    created_at: datetime
