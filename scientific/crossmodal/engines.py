"""Cross-modal CNV↔RNA and mutation↔RNA association engines."""

from scipy import stats as sp_stats

from packages.schemas.finding import AssociationResult, NonEstimableResult
from packages.statistics.core import benjamini_hochberg


def cnv_rna(
    cnv_rows: list[dict],
    rna_rows: list[dict],
    eligible_sample_ids: set[str],
    genes: tuple[str, ...] | None = None,
) -> dict:
    """Pearson correlation of CNV value vs RNA expression per (case, sample, gene)."""
    cnv = {}
    for r in cnv_rows:
        key = (r.get("case_id"), r.get("sample_id"), r.get("gene_id"))
        if r.get("sample_id") in eligible_sample_ids:
            if key in cnv and cnv[key] != r:
                raise ValueError(f"Conflicting duplicate for cnv key {key}")
            cnv.setdefault(key, r)
    rna = {}
    for r in rna_rows:
        key = (r.get("case_id"), r.get("sample_id"), r.get("gene_id"))
        if r.get("sample_id") in eligible_sample_ids:
            if key in rna and rna[key] != r:
                raise ValueError(f"Conflicting duplicate for rna key {key}")
            rna.setdefault(key, r)

    common = sorted(cnv.keys() & rna.keys())
    if genes is not None:
        common = [k for k in common if k[2] in genes]
    gene_pairs = {}
    for key in common:
        gid = key[2]
        gene_pairs.setdefault(gid, []).append(key)

    interim = []
    for _gene, keys in sorted(gene_pairs.items()):
        if len(keys) < 4:
            continue
        cnv_vals = [
            cnv[k].get("cnv_value", 0) if cnv[k].get("cnv_value") is not None else 0
            for k in keys
        ]
        rna_vals = [
            rna[k].get("value", 0) if rna[k].get("value") is not None else 0
            for k in keys
        ]
        r, p = sp_stats.pearsonr(cnv_vals, rna_vals)
        _case_ids = tuple(sorted({k[0] for k in keys}))
        sample_ids = tuple(sorted({k[1] for k in keys}))
        interim.append((_gene, keys, r, p, _case_ids, sample_ids))

    if not interim:
        return {"result": NonEstimableResult(
            reason="insufficient_common_pairs"
        ).model_dump(mode="json")}

    p_values = [x[3] for x in interim]
    q_values = benjamini_hochberg(p_values)

    findings = []
    for (_gene, keys, r, p, _case_ids, sample_ids), q in zip(interim, q_values, strict=False):
        findings.append(AssociationResult(
            test="pearson",
            effect=float(r),
            confidence_interval=(0.0, 0.0),
            p=float(p),
            q=float(q),
            group_ids={"all": sample_ids},
            group_n={"all": len(keys)},
        ))
    return {"findings": [f.model_dump(mode="json") for f in findings]}


def mutation_rna(
    mutation_rows: list[dict],
    rna_rows: list[dict],
    eligible_sample_ids: set[str],
    variant_classes: tuple[str, ...] = (),
    genes: tuple[str, ...] | None = None,
) -> dict:
    """Welch t-test comparing RNA expression between mutated and non-mutated cases per gene."""
    mutations_by_gene = {}
    for m in mutation_rows:
        gid = m.get("gene_id")
        cid = m.get("case_id")
        if gid and cid and (
                not variant_classes
                or m.get("variant_classification") in variant_classes
            ):
            if genes is not None and gid not in genes:
                continue
            mutations_by_gene.setdefault(gid, set()).add(cid)

    rna_by_case = {}
    for r in rna_rows:
        cid = r.get("case_id")
        gid = r.get("gene_id")
        if cid and gid and r.get("sample_id") in eligible_sample_ids:
            rna_by_case.setdefault((cid, gid), []).append(r.get("value", 0))

    findings = []
    for gid, mutated_cases in sorted(mutations_by_gene.items()):
        mutated_values = []
        nonmut_values = []
        mutated_ids = []
        nonmut_ids = []
        all_cases_with_rna = {cid for (cid, _gid) in rna_by_case if _gid == gid}
        for cid in sorted(all_cases_with_rna):
            vals = rna_by_case.get((cid, gid), [])
            if not vals:
                continue
            if cid in mutated_cases:
                mutated_values.extend(vals)
                mutated_ids.append(cid)
            else:
                nonmut_values.extend(vals)
                nonmut_ids.append(cid)
        if len(mutated_values) < 2 or len(nonmut_values) < 2:
            continue
        t_stat, p_val = sp_stats.ttest_ind(mutated_values, nonmut_values, equal_var=False)
        findings.append(AssociationResult(
            test="welch_t",
            effect=float(t_stat),
            confidence_interval=(0.0, 0.0),
            p=float(p_val),
            group_ids={"mutated": tuple(mutated_ids), "nonmutated": tuple(nonmut_ids)},
            group_n={"mutated": len(mutated_values), "nonmutated": len(nonmut_values)},
        ))
    return {"findings": [f.model_dump(mode="json") for f in findings]}