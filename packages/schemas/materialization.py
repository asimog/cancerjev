from typing import Literal

from pydantic import Field

from packages.schemas.identity import StrictRecord


class MaterializationRequest(StrictRecord):
    snapshot_id: str
    source_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    expected_source_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    modality: Literal["mutation", "expression", "cnv", "segment_cnv", "clinical"]
    parser_version: str = "1"
    measurement_type: str = ""
