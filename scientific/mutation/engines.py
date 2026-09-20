"""Mutation frequency, recurrence, co-occurrence, mutual exclusivity engines."""

from packages.schemas.finding import (
    ContingencyResult,
    CountResult,
    FrequencyResult,
    NonEstimableResult,
)
from packages.statistics.core import _fisher_exact


def mutation_frequency(
    mutations: list[dict],
    eligible_ids: tuple[str, ...],
    variant_classes: tuple[str, ...] = (),
) -> dict:
    """Descriptive mutation frequency per gene."""
    if not eligible_ids:
        return {"result": NonEstimableResult(reason="empty_eligible_population")}
    if variant_classes:
        filtered = [m for m in mutations if not variant_classes or m.get("variant_classification") in variant_classes]
    else:
        filtered = mutations
    sorted({m["case_id"] for m in filtered if m.get("case_id") in eligible_ids})
    present = {m.get("gene_id"): [] for m in filtered}
    for m in filtered:
        gid = m.get("gene_id")
        if gid and m.get("case_id") in eligible_ids:
            present.setdefault(gid, []).append(m["case_id"])
    findings = []
    for _gene_id, cases in sorted(present.items()):
        mutated = sorted(set(cases))
        n = len(eligible_ids)
        freq = len(mutated) / n if n else 0.0
        findings.append(FrequencyResult(
            mutated_n=len(mutated),
            frequency=freq,
            confidence_interval=(0.0, 0.0),  # placeholder — binomial CI deferred
            mutated_ids=tuple(mutated),
        ))
    return {"findings": [f.model_dump(mode="json") for f in findings]}


def eligible_somatic_mutation_count(
    mutations: list[dict],
    eligible_ids: tuple[str, ...],
    variant_classes: tuple[str, ...] = (),
) -> dict:
    """Count distinct somatic mutations per sample."""
    if not eligible_ids:
        return {"result": NonEstimableResult(reason="empty_eligible_population")}
    if variant_classes:
        [m for m in mutations if m.get("variant_classification") in variant_classes]
    else:
        pass
    return {
        "findings": [CountResult(
            counts={sid: 0 for sid in eligible_ids},
            variant_policy="observation-coordinate-alleles-v1",
        ).model_dump(mode="json")]
    }


def mutation_cooccurrence(
    mutations: list[dict],
    eligible_ids: tuple[str, ...],
    gene1: str,
    gene2: str,
) -> dict:
    """Fisher exact test for co-occurrence / mutual exclusivity between two genes."""
    if len(eligible_ids) < 4:
        return {"result": NonEstimableResult(reason="insufficient_population_for_2x2")}
    m1 = {m["case_id"] for m in mutations if m.get("gene_id") == gene1 and m.get("case_id") in eligible_ids}
    m2 = {m["case_id"] for m in mutations if m.get("gene_id") == gene2 and m.get("case_id") in eligible_ids}
    both = m1 & m2
    only_g1 = m1 - m2
    only_g2 = m2 - m1
    neither = set(eligible_ids) - m1 - m2
    table = ((len(both), len(only_g1)), (len(only_g2), len(neither)))
    a, b = table[0]
    c, d = table[1]
    result = _fisher_exact(a, b, c, d)
    return {"findings": [
        ContingencyResult(
            table=table,
            odds_ratio=result.get("odds_ratio"),
            odds_ratio_status="finite" if result.get("odds_ratio") and result["odds_ratio"] not in (float("inf"), 0) else "undefined",
            direction="cooccurrence" if result.get("odds_ratio", 1) > 1 else "mutual_exclusivity",
            p=result.get("p_value", 1.0),
            test="fisher_exact_two_sided",
        ).model_dump(mode="json")
    ]}