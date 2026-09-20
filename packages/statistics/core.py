import numpy as np
from scipy import stats


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    values = np.asarray(p_values, dtype=float)
    if np.any(~np.isfinite(values)) or np.any((values < 0) | (values > 1)):
        raise ValueError("p-values must be finite and in [0, 1]")
    order = np.argsort(values, kind="stable")
    ranked = values[order]
    adjusted = np.minimum.accumulate((ranked * len(values) / np.arange(1, len(values) + 1))[::-1])[
        ::-1
    ]
    result = np.empty_like(adjusted)
    result[order] = np.clip(adjusted, 0, 1)
    return result.tolist()


def frequency(present: list[bool]) -> float:
    if not present:
        raise ValueError("empty cohort")
    return float(np.mean(present))


def expression_variance(values: list[float]) -> float:
    return float(np.var(values, ddof=1)) if len(values) > 1 else 0.0


def expression_outliers(values: list[float], threshold: float = 3.5) -> list[bool]:
    array = np.asarray(values)
    median = np.median(array)
    mad = stats.median_abs_deviation(array)
    if mad == 0:
        return [False] * len(values)
    return (np.abs(0.6745 * (array - median) / mad) > threshold).tolist()


def _fisher_exact(a: int, b: int, c: int, d: int) -> dict:
    """Two-sided Fisher exact test for a 2x2 contingency table."""
    if min(a, b, c, d) < 0:
        raise ValueError("negative cell counts")
    table = [[a, b], [c, d]]
    odds_ratio, p_value = stats.fisher_exact(table)
    return {"odds_ratio": float(odds_ratio), "p_value": float(p_value)}
