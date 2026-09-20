from collections import defaultdict

from pydantic import BaseModel, ConfigDict

from packages.schemas.identity import CaseRecord, FileRecord, FileSampleLink


class CoverageRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    case_id: str
    mutation: bool
    cnv: bool
    rna: bool
    clinical: bool


def modality(file: FileRecord) -> str | None:
    text = f"{file.data_category} {file.data_type}".lower()
    if "mutation" in text or "masked somatic" in text:
        return "mutation"
    if "copy number" in text:
        return "cnv"
    if "gene expression" in text or "transcriptome profiling" in text:
        return "rna"
    if "clinical" in text:
        return "clinical"
    return None


def build_coverage(
    cases: list[CaseRecord], files: list[FileRecord], links: list[FileSampleLink]
) -> list[CoverageRecord]:
    by_file = {item.file_id: modality(item) for item in files}
    covered: dict[str, set[str]] = defaultdict(set)
    for link in links:
        if by_file.get(link.file_id):
            covered[link.case_id].add(by_file[link.file_id])  # type: ignore[arg-type]
    return [
        CoverageRecord(
            case_id=c.case_id,
            **{m: m in covered[c.case_id] for m in ("mutation", "cnv", "rna", "clinical")},
        )
        for c in sorted(cases, key=lambda x: x.case_id)
    ]
