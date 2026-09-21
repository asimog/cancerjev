import pytest

from scientific.crossmodal import EngineContext, analyze_cnv_rna


def make_context(**overrides) -> EngineContext:
    values = dict(
        snapshot_id="DS-X",
        snapshot_hash="sha256:" + "1" * 64,
        cohort_id="CO-1",
        cohort_content_hash="sha256:" + "2" * 64,
        cohort_size=25,
        engine_version="1",
        method_version="cnv-rna-v1",
        parameters={"min_pairs": 4},
        input_hashes=("sha256:" + "a" * 64,),
        environment={"python": "3.12", "numpy": "2.0", "scipy": "1.14"},
    )
    values.update(overrides)
    return EngineContext(**values)


def rows(count: int = 20, gene: str = "ENSG1"):
    cnv = [
        {
            "case_id": f"c{i:02d}",
            "sample_id": f"s{i:02d}",
            "gene_id": gene,
            "cnv_value": i,
        }
        for i in range(count)
    ]
    rna = [
        {
            "case_id": f"c{i:02d}",
            "sample_id": f"s{i:02d}",
            "gene_id": gene,
            "value": 2 * i + 1,
        }
        for i in range(count)
    ]
    return cnv, rna


def test_known_cnv_rna_relationship_and_missingness() -> None:
    cnv, rna = rows(20)
    rna.append({"case_id": "c00", "sample_id": "other", "gene_id": "ENSG1", "value": -9})
    finding = analyze_cnv_rna(make_context(), cnv, rna)[0]
    assert finding.eligible_cases == 20
    assert finding.eligible_case_ids == tuple(f"c{i:02d}" for i in range(20))
    assert finding.n_effective == 20
    assert finding.missing_n == 5
    assert finding.effect_size > 0.999
    assert finding.q_value < 1e-20
    assert finding.analysis_version == "cnv-rna-v1"


def test_duplicate_biological_keys_fail_deterministically() -> None:
    cnv, rna = rows(4)
    with pytest.raises(ValueError, match="duplicate_cnv_key"):
        analyze_cnv_rna(make_context(), cnv + [dict(cnv[0])], rna)
    with pytest.raises(ValueError, match="duplicate_rna_key"):
        analyze_cnv_rna(make_context(), cnv, rna + [dict(rna[0])])


def test_eligibility_describes_the_post_filter_population() -> None:
    cnv, rna = rows(6)
    cnv[0]["cnv_value"] = float("nan")
    rna[1]["value"] = None
    finding = analyze_cnv_rna(make_context(), cnv, rna)[0]
    # NaN and missing rows are excluded before the statistic and before the counts.
    assert finding.eligible_cases == 4
    assert "c00" not in finding.eligible_case_ids and "c01" not in finding.eligible_case_ids
    assert finding.n_effective == 4
    assert finding.missing_n == 21

    cnv, rna = rows(5)
    cnv[0]["cnv_value"] = float("nan")
    cnv[1]["cnv_value"] = float("inf")
    # Three finite pairs fall below the minimum; the gene is not tested at all.
    assert analyze_cnv_rna(make_context(), cnv, rna) == []


def test_untestable_genes_are_skipped_not_fatal() -> None:
    cnv, rna = rows(6)
    constant_cnv = [row | {"gene_id": "ENSG2", "cnv_value": 1.0} for row in rows(6)[0]]
    constant_rna = [row | {"gene_id": "ENSG2"} for row in rows(6)[1]]
    findings = analyze_cnv_rna(make_context(), cnv + constant_cnv, rna + constant_rna)
    # Zero-variance ENSG2 is untestable and skipped; ENSG1 still produces a finding.
    assert [finding.gene for finding in findings] == ["ENSG1"]


def test_identity_binds_every_material_input() -> None:
    cnv, rna = rows(20)
    base = analyze_cnv_rna(make_context(), cnv, rna)[0].result_hash

    def changed(**overrides) -> str:
        return analyze_cnv_rna(make_context(**overrides), cnv, rna)[0].result_hash

    assert changed(input_hashes=("sha256:" + "b" * 64,)) != base
    assert changed(cohort_id="CO-2") != base
    assert changed(cohort_content_hash="sha256:" + "3" * 64) != base
    assert changed(parameters={"min_pairs": 5}) != base
    assert changed(engine_version="2") != base
    assert changed(method_version="cnv-rna-v2") != base
    assert changed(environment={"python": "3.13", "numpy": "2.0", "scipy": "1.14"}) != base
    assert changed(snapshot_hash="sha256:" + "9" * 64) != base
    assert changed(cohort_size=26) != base  # changes missingness output
    # The tested family identity changes with the gene.
    other_gene = analyze_cnv_rna(make_context(), rows(20, "ENSG2")[0], rows(20, "ENSG2")[1])
    assert other_gene[0].result_hash != base

    # Reordering input rows never changes identity.
    shuffled_cnv = list(reversed(cnv))
    shuffled_rna = sorted(rna, key=lambda row: row["case_id"], reverse=True)
    reordered = analyze_cnv_rna(make_context(), shuffled_cnv, shuffled_rna)[0].result_hash
    assert reordered == base

    # A different statistical output changes identity; raw row values are
    # otherwise bound through the input artifact hashes above.
    noisy = [row | {"value": row["value"] + (7 if i % 2 else -7)} for i, row in enumerate(rna)]
    assert analyze_cnv_rna(make_context(), cnv, noisy)[0].result_hash != base


def test_multiple_testing_family_covers_tested_genes() -> None:
    cnv_a, rna_a = rows(20, "ENSG1")
    cnv_b = [row | {"gene_id": "ENSG2", "cnv_value": -row["cnv_value"]} for row in rows(20)[0]]
    rna_b = rows(20, "ENSG2")[1]
    findings = analyze_cnv_rna(make_context(), cnv_a + cnv_b, rna_a + rna_b)
    assert [finding.gene for finding in findings] == ["ENSG1", "ENSG2"]
    # Two tested genes: the BH family inflates the raw p-values.
    assert all(finding.q_value >= finding.p_value for finding in findings)
    assert len({finding.result_hash for finding in findings}) == 2
