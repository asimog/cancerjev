"""RNA expression variance, outlier, and group comparison engines."""
import numpy as np
from scipy import stats as sp_stats

from packages.schemas.finding import AssociationResult, NonEstimableResult, OutlierResult
from packages.statistics.core import expression_outliers, expression_variance


def rna_outlier(
    expression_rows: list[dict],
    eligible_ids: tuple[str, ...],
    threshold: float = 3.5,
    measurement_type: str = "",
    genes: tuple[str, ...] | None = None,
) -> dict:
    if not eligible_ids:
        return {
            "result": NonEstimableResult(reason="empty_eligible_population").model_dump(mode="json")
        }
    if not expression_rows:
        return {
            "result": NonEstimableResult(reason="no_expression_data").model_dump(mode="json")
        }

    gene_obs = {}
    for r in expression_rows:
        sid = r.get("sample_id")
        gid = r.get("gene_id")
        val = r.get("value")
        if sid in eligible_ids and gid and isinstance(val, (int, float)):
            if genes is not None and gid not in genes:
                continue
            gene_obs.setdefault(gid, []).append((sid, gid, val))

    if not gene_obs:
        return {
            "result": NonEstimableResult(reason="no_finite_values").model_dump(mode="json")
        }

    findings = []
    for _gid, obs in sorted(gene_obs.items()):
        if len(obs) < 3:
            continue
        values = [o[2] for o in obs]
        variance = expression_variance(values)
        median = float(np.median(values))
        mad = float(sp_stats.median_abs_deviation(values))
        if mad == 0:
            findings.append(OutlierResult(
                center=median,
                mad=0.0,
                variance=variance,
                threshold=threshold,
                status="zero_mad",
                outlier_ids=(),
            ).model_dump(mode="json"))
            continue
        outlier_flags = expression_outliers(values, threshold)
        outlier_ids = tuple(sorted([obs[i][0] for i, flag in enumerate(outlier_flags) if flag]))
        findings.append(OutlierResult(
            center=median,
            mad=mad,
            variance=variance,
            threshold=threshold,
            status="estimable",
            outlier_ids=outlier_ids,
        ).model_dump(mode="json"))

    return {"findings": findings}


def cohort_comparison(
    group1_values: list[float],
    group2_values: list[float],
    group1_ids: tuple[str, ...],
    group2_ids: tuple[str, ...],
) -> dict:
    if len(group1_values) < 2 or len(group2_values) < 2:
        return {"result": NonEstimableResult(
            reason="insufficient_group_size"
        ).model_dump(mode="json")}
    t_stat, p_value = sp_stats.ttest_ind(group1_values, group2_values, equal_var=False)
    return {"findings": [
        AssociationResult(
            test="welch_t",
            effect=float(t_stat),
            confidence_interval=(0.0, 0.0),
            p=float(p_value),
            group_ids={"group1": group1_ids, "group2": group2_ids},
            group_n={"group1": len(group1_values), "group2": len(group2_values)},
        ).model_dump(mode="json")
    ]}