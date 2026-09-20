from scientific.crossmodal import analyze_cnv_rna


def test_known_cnv_rna_relationship_and_matching() -> None:
    cnv = [
        {"case_id": f"c{i}", "sample_id": f"s{i}", "gene_id": "ENSG1", "cnv_value": i}
        for i in range(20)
    ]
    rna = [
        {"case_id": f"c{i}", "sample_id": f"s{i}", "gene_id": "ENSG1", "value": 2 * i + 1}
        for i in range(20)
    ] + [{"case_id": "c0", "sample_id": "other", "gene_id": "ENSG1", "value": -9}]
    finding = analyze_cnv_rna("DS-X", 25, cnv, rna, ["sha256:" + "a" * 64])[0]
    assert finding.eligible_cases == 20
    assert finding.missing_n == 5
    assert finding.effect_size > 0.999
    assert finding.q_value < 1e-20
