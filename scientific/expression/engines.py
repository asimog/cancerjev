"""RNA expression variance, outlier, and group comparison engines."""

from scipy import stats as sp_stats

from packages.schemas.finding import AssociationResult, NonEstimableResult, OutlierResult
from packages.statistics.core import expression_outliers, expression_variance


def rna_outlier(
    expression_rows: list[dict],
    eligible_ids: tuple[str, ...],
    threshold: float = 3.5,
    measurement_type: str = "",
) -> dict:
    if not eligible_ids:
        return {"result": NonEstimableResult(reason="empty_eligible_population")}
    if not expression_rows:
        return {"result": NonEstimableResult(reason="no_expression_data")}
    values = [r["value"] for r in expression_rows if r.get("sample_id") in eligible_ids and isinstance(r.get("value"), (int, float))]
    if not values:
        return {"result": NonEstimableResult(reason="no_finite_values")}
    values_arr = values
    var = expression_variance(values_arr)
    median = float(sp_stats.median_abs_deviation(values_arr))
    mad = median
    if mad == 0:
        return {"findings": [
            OutlierResult(
                center=float(sp_stats.median_abs_deviation(values_arr)),
                mad=0.0,
                variance=var,
                threshold=threshold,
                status="zero_mad",
                outlier_ids=(),
            ).model_dump(mode="json")
        ]}
    outliers = expression_outliers(values_arr, threshold)
    outlier_ids = tuple(sorted([expression_rows[i]["sample_id"] for i, o in enumerate(outliers) if o]))
    return {"findings": [
        OutlierResult(
            center=float(np.median(values_arr)),
            mad=mad,
            variance=var,
            threshold=threshold,
            status="estimable",
            outlier_ids=outlier_ids,
        ).model_dump(mode="json")
    ]}


import numpy as np


def cohort_comparison(
    group1_values: list[float],
    group2_values: list[float],
    group1_ids: tuple[str, ...],
    group2_ids: tuple[str, ...],
) -> dict:
    if len(group1_values) < 2 or len(group2_values) < 2:
        return {"result": NonEstimableResult(reason="insufficient_group_size")}
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