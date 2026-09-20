from collections import defaultdict

from packages.provenance.hashing import canonical_hash
from packages.schemas.finding import Finding
from packages.statistics import benjamini_hochberg, cnv_expression


def analyze_cnv_rna(
    snapshot_id: str,
    cohort_size: int,
    cnv_rows: list[dict],
    rna_rows: list[dict],
    input_hashes: list[str],
) -> list[Finding]:
    """Inner-join exact case/sample/gene identity and disclose every eligible population."""
    cnv = {(r["case_id"], r["sample_id"], r["gene_id"]): r for r in cnv_rows}
    rna = {(r["case_id"], r["sample_id"], r["gene_id"]): r for r in rna_rows}
    pairs = defaultdict(list)
    for key in sorted(cnv.keys() & rna.keys()):
        pairs[key[2]].append((key, cnv[key], rna[key]))
    interim = []
    for gene, rows in sorted(pairs.items()):
        if len(rows) < 4:
            continue
        result = cnv_expression([r[1]["cnv_value"] for r in rows], [r[2]["value"] for r in rows])
        interim.append((gene, rows, result))
    q_values = benjamini_hochberg([r.p_value for _, _, r in interim])
    findings = []
    for (gene, rows, result), q in zip(interim, q_values, strict=True):
        cases = tuple(sorted({row[0][0] for row in rows}))
        samples = tuple(sorted({row[0][1] for row in rows}))
        identity = {
            "snapshot_id": snapshot_id,
            "gene": gene,
            "effect": result.effect_size,
            "p": result.p_value,
            "q": q,
            "cases": cases,
            "analysis": "cnv-rna-v1",
        }
        result_hash = canonical_hash(identity)
        findings.append(
            Finding(
                finding_id=f"F-{result_hash[-12:]}",
                snapshot_id=snapshot_id,
                finding_type="cnv_expression_association",
                gene=gene,
                cohort_size=cohort_size,
                eligible_cases=len(cases),
                eligible_case_ids=cases,
                eligible_sample_ids=samples,
                effect_size=result.effect_size,
                confidence_interval=result.confidence_interval,
                p_value=result.p_value,
                q_value=q,
                missing_n=cohort_size - len(cases),
                missing_fraction=(cohort_size - len(cases)) / cohort_size if cohort_size else 0,
                analysis_version="cnv-rna-v1",
                input_object_hashes=tuple(sorted(input_hashes)),
                result_hash=result_hash,
            )
        )
    return findings
