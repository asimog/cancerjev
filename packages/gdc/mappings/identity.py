from packages.schemas.identity import (
    AliquotRecord,
    CaseRecord,
    FileRecord,
    FileSampleLink,
    SampleRecord,
)


def map_file_hit(
    hit: dict,
) -> tuple[
    FileRecord, list[CaseRecord], list[SampleRecord], list[AliquotRecord], list[FileSampleLink]
]:
    if hit.get("access") != "open":
        raise ValueError("controlled-access GDC file rejected")
    analysis = hit.get("analysis") or {}
    file = FileRecord(
        **{
            k: hit.get(k)
            for k in (
                "file_id",
                "file_name",
                "file_size",
                "md5sum",
                "access",
                "data_category",
                "data_type",
                "data_format",
                "experimental_strategy",
            )
        },
        workflow_type=analysis.get("workflow_type"),
    )
    cases, samples, aliquots, links = [], [], [], []
    for case in hit.get("cases") or []:
        case_id = case["case_id"]
        cases.append(
            CaseRecord(
                case_id=case_id,
                submitter_id=case.get("submitter_id"),
                project_id=(case.get("project") or {})["project_id"],
            )
        )
        case_samples = case.get("samples") or []
        if not case_samples:
            links.append(FileSampleLink(file_id=file.file_id, case_id=case_id))
        for sample in case_samples:
            sid = sample["sample_id"]
            samples.append(
                SampleRecord(
                    sample_id=sid,
                    case_id=case_id,
                    sample_submitter_id=sample.get("submitter_id"),
                    sample_type=sample.get("sample_type"),
                    tumor_descriptor=sample.get("tumor_descriptor"),
                    tissue_type=sample.get("tissue_type"),
                )
            )
            found = []
            for portion in sample.get("portions") or []:
                for analyte in portion.get("analytes") or []:
                    for aliquot in analyte.get("aliquots") or []:
                        aid = aliquot["aliquot_id"]
                        found.append(aid)
                        aliquots.append(
                            AliquotRecord(
                                aliquot_id=aid,
                                sample_id=sid,
                                submitter_id=aliquot.get("submitter_id"),
                            )
                        )
            for aid in found or [None]:
                links.append(
                    FileSampleLink(
                        file_id=file.file_id, case_id=case_id, sample_id=sid, aliquot_id=aid
                    )
                )
    return file, cases, samples, aliquots, links
