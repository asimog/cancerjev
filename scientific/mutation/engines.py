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
    genes: tuple[str, ...] | None = None,
) -> dict:
    """Descriptive mutation frequency per gene."""
    if not eligible_ids:
        return {"result": NonEstimableResult(
            reason="empty_eligible_population"
        ).model_dump(mode="json")}
    if variant_classes:
        filtered = [m for m in mutations if m.get("variant_classification") in variant_classes]
    else:
        filtered = mutations
    if genes is not None:
        filtered = [m for m in filtered if m.get("gene_id") in genes]
    sorted({m["case_id"] for m in filtered if m.get("case_id") in eligible_ids})
    present = {}
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
    genes: tuple[str, ...] | None = None,
) -> dict:
    """Count distinct somatic mutations per sample."""
    if not eligible_ids:
        return {"result": NonEstimableResult(
            reason="empty_eligible_population"
        ).model_dump(mode="json")}
    filtered = mutations
    if variant_classes:
        filtered = [m for m in filtered if m.get("variant_classification") in variant_classes]
    if genes is not None:
        filtered = [m for m in filtered if m.get("gene_id") in genes]
    sample_mutations: dict[str, set[tuple]] = {}
    for m in filtered:
        sid = m.get("sample_id")
        if sid not in eligible_ids:
            continue
        key = (
            m.get("chromosome"),
            m.get("start"),
            m.get("end"),
            m.get("reference"),
            m.get("alternate"),
        )
        sample_mutations.setdefault(sid, set()).add(key)
    counts = {sid: len(sample_mutations.get(sid, set())) for sid in eligible_ids}
    return {
        "findings": [CountResult(
            counts=counts,
            variant_policy="observation-coordinate-alleles-v1",
        ).model_dump(mode="json")]
    }


def mutation_cooccurrence(
    mutations: list[dict],
    eligible_ids: tuple[str, ...],
    gene1: str,
    gene2: str,
    genes: tuple[str, ...] | None = None,
) -> dict:
    """Fisher exact test for co-occurrence / mutual exclusivity between two genes."""
    if genes is not None:
        if len(genes) != 2:
            return {"result": NonEstimableResult(
            reason="genes_must_contain_exactly_2"
        ).model_dump(mode="json")}
        gene1, gene2 = genes[0], genes[1]
    if len(eligible_ids) < 4:
        return {"result": NonEstimableResult(
            reason="insufficient_population_for_2x2"
        ).model_dump(mode="json")}
    m1 = {
        m["case_id"]
        for m in mutations
        if m.get("gene_id") == gene1 and m.get("case_id") in eligible_ids
    }
    m2 = {
        m["case_id"]
        for m in mutations
        if m.get("gene_id") == gene2 and m.get("case_id") in eligible_ids
    }
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
            odds_ratio_status=(
                "finite"
                if result.get("odds_ratio")
                and result["odds_ratio"] not in (float("inf"), 0)
                else "undefined"
            ),
            direction="cooccurrence" if result.get("odds_ratio", 1) > 1 else "mutual_exclusivity",
            p=result.get("p_value", 1.0),
            test="fisher_exact_two_sided",
        ).model_dump(mode="json")
    ]}