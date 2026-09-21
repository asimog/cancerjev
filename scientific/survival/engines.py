"""Versioned survival endpoint construction, KM, log-rank, Cox engines."""

import numpy as np

from packages.schemas.finding import SurvivalCurve, SurvivalResult
from packages.statistics.endpoints import ENDPOINT_VERSION
from packages.statistics.endpoints import endpoint as clinical_endpoint


def survival(
    clinical_rows: list[dict],
    group_ids: dict[str, tuple[str, ...]],
    group_labels: dict[str, str],
) -> dict:
    """Kaplan-Meier survival analysis with log-rank test between groups."""
    from lifelines import KaplanMeierFitter
    from lifelines.statistics import logrank_test

    # Build endpoints per case
    endpoints = {}
    for row in clinical_rows:
        case_id = row.get("case_id")
        result, error = clinical_endpoint(row)
        if error:
            continue
        value, event = result
        endpoints[case_id] = {"T": float(value), "E": int(event)}

    curves = {}
    all_groups = []
    all_times = []
    all_events = []

    for label, ids in group_ids.items():
        valid = [(endpoints[cid]["T"], endpoints[cid]["E"]) for cid in ids if cid in endpoints]
        if not valid:
            continue
        times, events = zip(*valid, strict=False)
        kmf = KaplanMeierFitter()
        kmf.fit(list(times), list(events))
        surv_at_times = kmf.survival_function_.iloc[:, 0]
        ci = kmf.confidence_interval_
        curves[label] = SurvivalCurve(
            n=len(times),
            events=int(sum(events)),
            censored=len(times) - int(sum(events)),
            median_survival=(
                float(kmf.median_survival_time_)
                if not np.isnan(kmf.median_survival_time_)
                else None
            ),
            median_status="estimated" if not np.isnan(kmf.median_survival_time_) else "not_reached",
            timeline=tuple(surv_at_times.index.tolist()),
            survival=tuple(surv_at_times.tolist()),
            lower=tuple(ci.iloc[:, 0].tolist()),
            upper=tuple(ci.iloc[:, 1].tolist()),
        )
        all_groups.extend([label] * len(times))
        all_times.extend(times)
        all_events.extend(events)

    if len(set(all_groups)) < 2:
        p_value = None
        test_status = "insufficient_groups"
    elif len(set(all_groups)) == 2:
        try:
            unique_groups = sorted(set(all_groups))
            group_a, group_b = unique_groups[0], unique_groups[1]
            times_a = [t for t, g in zip(all_times, all_groups, strict=True) if g == group_a]
            events_a = [e for e, g in zip(all_events, all_groups, strict=True) if g == group_a]
            times_b = [t for t, g in zip(all_times, all_groups, strict=True) if g == group_b]
            events_b = [e for e, g in zip(all_events, all_groups, strict=True) if g == group_b]
            result = logrank_test(times_a, times_b, events_a, events_b)
            p_value = float(result.p_value)
            test_status = "estimable"
        except Exception:
            p_value = None
            test_status = "non_estimable"
    else:
        p_value = None
        test_status = "non_estimable"

    return {"findings": [
        SurvivalResult(
            endpoint_version=ENDPOINT_VERSION,
            curves=curves,
            group_ids=group_ids,
            test="logrank",
            test_status=test_status,
            p=p_value,
        ).model_dump(mode="json")
    ]}