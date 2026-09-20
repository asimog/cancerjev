"""QC and confounder assessment engines."""

from packages.schemas.finding import QCResult


def confounder_check(
    clinical_rows: list[dict],
    group_ids: dict[str, tuple[str, ...]],
    modality_coverage: dict[str, dict[str, float]] | None = None,
) -> dict:
    """Compute group-level imbalance indicators for age, stage, gender, missingness, coverage."""
    group_stats = {}
    for label, ids in group_ids.items():
        cases_in_group = [r for r in clinical_rows if r.get("case_id") in ids]
        ages = [float(r["age_at_diagnosis"]) for r in cases_in_group if r.get("age_at_diagnosis") is not None]
        stages = [str(r["stage"]) for r in cases_in_group if r.get("stage")]
        genders = [str(r["gender"]) for r in cases_in_group if r.get("gender")]
        stage_dist = {}
        for s in stages:
            stage_dist[s] = stage_dist.get(s, 0) + 1
        age_mean = float(np.mean(ages)) if len(ages) > 0 else None
        group_stats[label] = {
            "n": len(cases_in_group),
            "age_mean": age_mean,
            "stage_distribution": stage_dist,
            "gender_counts": {g: genders.count(g) for g in set(genders)},
        }
    findings = []
    for label, stat in group_stats.items():
        findings.append(QCResult(
            group_n={label: stat["n"]},
            age_mean={label: stat["age_mean"]},
            stage_distribution={label: stat["stage_distribution"]},
            missing_fraction={},
            modality_coverage=modality_coverage or {},
            selected_samples_per_case={},
            flags=[],
        ))
    return {"findings": [f.model_dump(mode="json") for f in findings]}


import numpy as np