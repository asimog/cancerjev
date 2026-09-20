from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class Association:
    effect_size: float
    p_value: float
    confidence_interval: tuple[float, float]
    n: int


def cnv_expression(cnv: list[float], expression: list[float]) -> Association:
    x, y = np.asarray(cnv, dtype=float), np.asarray(expression, dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    x, y = x[valid], y[valid]
    if len(x) < 4 or np.ptp(x) == 0 or np.ptp(y) == 0:
        raise ValueError("insufficient variable pairs")
    result = stats.pearsonr(x, y)
    r = float(result.statistic)
    ci = result.confidence_interval(0.95)
    return Association(r, float(result.pvalue), (float(ci.low), float(ci.high)), len(x))


def mutation_expression(mutated: list[bool], expression: list[float]) -> Association:
    m, y = np.asarray(mutated, dtype=bool), np.asarray(expression, dtype=float)
    valid = np.isfinite(y)
    m, y = m[valid], y[valid]
    a, b = y[m], y[~m]
    if min(len(a), len(b)) < 2:
        raise ValueError("both groups require two measurements")
    result = stats.ttest_ind(a, b, equal_var=False)
    effect = float(np.mean(a) - np.mean(b))
    se = np.sqrt(np.var(a, ddof=1) / len(a) + np.var(b, ddof=1) / len(b))
    return Association(
        effect, float(result.pvalue), (effect - 1.96 * se, effect + 1.96 * se), len(y)
    )
