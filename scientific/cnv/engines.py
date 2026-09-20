from packages.schemas.finding import CNVFrequencyResult, NonEstimableResult


def cnv_frequency(
    cnv_rows: list[dict],
    eligible_ids: tuple[str, ...],
    amplification_threshold: float = 0.2,
    deletion_threshold: float = -0.2,
) -> dict:
    if not eligible_ids:
        return {"result": NonEstimableResult(reason="empty_eligible_population")}
    gene_data = {}
    for row in cnv_rows:
        gid = row.get("gene_id")
        sid = row.get("sample_id")
        if gid and sid in eligible_ids:
            val = row.get("cnv_value")
            if val is not None:
                gene_data.setdefault(gid, {"amp": [], "del": [], "ids": []})
                if val >= amplification_threshold:
                    gene_data[gid]["amp"].append(sid)
                elif val <= deletion_threshold:
                    gene_data[gid]["del"].append(sid)
                gene_data[gid]["ids"].append(sid)
    findings = []
    for _gid, dat in sorted(gene_data.items()):
        n = len(set(dat["ids"]))
        findings.append(CNVFrequencyResult(
            amplification_n=len(set(dat["amp"])),
            deletion_n=len(set(dat["del"])),
            amplification_frequency=len(set(dat["amp"])) / n if n else 0.0,
            deletion_frequency=len(set(dat["del"])) / n if n else 0.0,
            amplification_ids=tuple(sorted(set(dat["amp"]))),
            deletion_ids=tuple(sorted(set(dat["del"]))),
            amplification_threshold=amplification_threshold,
            deletion_threshold=deletion_threshold,
        ))
    return {"findings": [f.model_dump(mode="json") for f in findings]}