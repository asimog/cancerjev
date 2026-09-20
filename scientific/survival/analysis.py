from dataclasses import dataclass

from lifelines import KaplanMeierFitter


@dataclass(frozen=True)
class SurvivalEstimate:
    median_survival: float
    n: int
    events: int


def kaplan_meier(days: list[float], events: list[bool]) -> SurvivalEstimate:
    if len(days) != len(events) or not days:
        raise ValueError("aligned non-empty survival vectors required")
    model = KaplanMeierFitter().fit(days, event_observed=events)
    return SurvivalEstimate(float(model.median_survival_time_), len(days), sum(events))
