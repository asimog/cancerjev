from packages.provenance.hashing import canonical_hash
from scientific.crossmodal import analyze_cnv_rna


def execute_analysis(payload: dict) -> dict:
    engine = payload.get("engine")
    if engine != "cnv_rna":
        raise ValueError(f"unsupported analysis engine: {engine}")
    findings = analyze_cnv_rna(
        payload["snapshot_id"],
        payload["cohort_size"],
        payload["cnv_rows"],
        payload["rna_rows"],
        payload["input_hashes"],
    )
    encoded = [finding.model_dump(mode="json") for finding in findings]
    return {"findings": encoded, "result_hash": canonical_hash(encoded)}
