import gzip
import hashlib
import json
from dataclasses import replace

import pyarrow.parquet as pq
import pytest

from packages.gdc.identity import FrozenIdentityResolver, IdentityError
from packages.gdc.materialization import materialize_verified
from packages.gdc.normalization import normalize_gene
from packages.gdc.parsers import MEASUREMENTS, PARSERS, select_parser
from packages.gdc.transfer import ChecksumMismatch
from packages.provenance.hashing import sha256_file
from packages.schemas.identity import FileSampleLink
from packages.schemas.materialization import MaterializationRequest


def run_fixture(gdc_fixture, tmp_path, name="rna.tsv", **kwargs):
    path, source, identity = gdc_fixture(name)
    modality = {
        "rna.tsv": "expression",
        "mutation.maf": "mutation",
        "gene_cnv.tsv": "cnv",
        "segment.tsv": "segment_cnv",
        "clinical.json": "clinical",
    }[name]
    return materialize_verified(
        path,
        tmp_path,
        source=source,
        identity=identity,
        expected_file_id=source.file_id if source else None,
        expected_sha256=sha256_file(str(path)),
        modality=modality,
        measurement=kwargs.pop("measurement", "tpm_unstranded" if modality == "expression" else ""),
        **kwargs,
    )


@pytest.mark.parametrize(
    "name", ["mutation.maf", "rna.tsv", "gene_cnv.tsv", "segment.tsv", "clinical.json"]
)
def test_real_gdc_excerpts(gdc_fixture, tmp_path, name):
    result = run_fixture(gdc_fixture, tmp_path, name)
    rows = pq.read_table(result.parquet).to_pylist()
    assert result.summary["rows_accepted"] == len(rows) > 0
    assert result.summary["rows_rejected"] == 0
    assert all(row["case_id"] for row in rows)
    if name == "mutation.maf":
        assert rows[0]["ssm_id"] is None
        assert rows[0]["aliquot_id"] == "3c6dcba5-1312-40ca-b589-07f7d88b3477"
        assert rows[0]["transcript_id"].startswith("ENST")
    if name == "gene_cnv.tsv":
        assert rows[0]["cnv_value"] is None and rows[0]["cnv_class"] is None
        assert rows[-1]["cnv_value"] == 2
        assert result.summary["samples_excluded"] == 1
    if name == "segment.tsv":
        assert rows[0]["probe_count"] == 1989
    if name == "clinical.json":
        assert "days_to_event" not in rows[0]
        assert rows[0]["stage"] == "Stage IIB"
        assert json.loads(rows[0]["diagnosis_json"])["diagnosis_id"] == rows[0]["diagnosis_id"]


def test_measurements_and_star_exclusions(gdc_fixture, tmp_path):
    hashes = set()
    for measurement in MEASUREMENTS:
        result = run_fixture(gdc_fixture, tmp_path / measurement, measurement=measurement)
        rows = pq.read_table(result.parquet).to_pylist()
        assert {row["measurement_type"] for row in rows} == {measurement}
        assert result.summary["rows_excluded"] == 4
        assert result.summary["reasons"] == {"star_summary_row": 4}
        assert all(row["source_gene_id"].startswith("ENSG") for row in rows)
        hashes.add(result.logical_sha256)
    assert len(hashes) == 6


def modified(gdc_fixture, tmp_path, transform, name="rna.tsv", **overrides):
    path, source, identity = gdc_fixture(name)
    altered = tmp_path / name
    altered.write_bytes(transform(path.read_bytes()))
    source = source.model_copy(
        update={
            "file_size": altered.stat().st_size,
            "md5sum": hashlib.md5(altered.read_bytes()).hexdigest(),
        }
        | overrides.pop("source_updates", {})
    )
    return materialize_verified(
        altered,
        tmp_path / "out",
        source=source,
        identity=overrides.pop("identity", identity),
        expected_file_id=overrides.pop("expected_file_id", source.file_id),
        expected_sha256=sha256_file(str(altered)),
        modality={
            "rna.tsv": "expression",
            "segment.tsv": "segment_cnv",
            "mutation.maf": "mutation",
            "gene_cnv.tsv": "cnv",
        }[name],
        measurement="unstranded" if name == "rna.tsv" else "",
        **overrides,
    )


def test_compressed_and_logical_batch_determinism(gdc_fixture, tmp_path):
    plain = run_fixture(gdc_fixture, tmp_path / "plain", measurement="unstranded", batch_size=1)
    compressed = modified(gdc_fixture, tmp_path, lambda b: gzip.compress(b, mtime=0), batch_size=3)
    assert plain.logical_sha256 == compressed.logical_sha256
    assert plain.max_buffered_rows == 1 and compressed.max_buffered_rows == 3


def test_empty_valid_schema_and_bad_header(gdc_fixture, tmp_path):
    empty = modified(gdc_fixture, tmp_path, lambda b: b"\n".join(b.splitlines()[:2]) + b"\n")
    assert pq.read_table(empty.parquet).num_rows == 0
    assert "measurement_type" in pq.read_schema(empty.parquet).names
    with pytest.raises(ValueError, match="malformed_header"):
        modified(gdc_fixture, tmp_path, lambda b: b.replace(b"gene_id", b"wrong", 1))


@pytest.mark.parametrize("update", [{"file_size": 1}, {"md5sum": "0" * 32}])
def test_frozen_verification_failure(gdc_fixture, tmp_path, update):
    with pytest.raises(ChecksumMismatch):
        modified(gdc_fixture, tmp_path, lambda b: b, source_updates=update)


def test_source_uuid_and_sha_mismatch(gdc_fixture, tmp_path):
    with pytest.raises(ValueError, match="association"):
        modified(gdc_fixture, tmp_path, lambda b: b, expected_file_id="wrong")
    path, source, identity = gdc_fixture("rna.tsv")
    with pytest.raises(ValueError, match="SHA256"):
        materialize_verified(
            path,
            tmp_path,
            source=source,
            identity=identity,
            expected_file_id=source.file_id,
            expected_sha256="sha256:" + "0" * 64,
            modality="expression",
            measurement="unstranded",
        )


def test_registry_is_explicit(gdc_fixture):
    _, source, _ = gdc_fixture("rna.tsv")
    for changes in (
        {"workflow_type": "unknown"},
        {"data_format": "CSV"},
        {"experimental_strategy": "WXS"},
    ):
        with pytest.raises(ValueError, match="unknown_parser"):
            select_parser(
                modality="expression",
                version="1",
                source=source.model_copy(update=changes),
                measurement="unstranded",
            )
    with pytest.raises(ValueError, match="unsupported_measurement"):
        select_parser(modality="expression", version="1", source=source, measurement="TPM")
    with pytest.raises(ValueError, match="unknown_parser"):
        select_parser(modality="expression", version="99", source=source)
    assert all(p.schema_version == "2" and p.identity_level for p in PARSERS)


def test_missing_and_ambiguous_identity(gdc_fixture, tmp_path):
    _, source, identity = gdc_fixture("rna.tsv")
    missing = replace(identity, links=())
    result = modified(gdc_fixture, tmp_path, lambda b: b, identity=missing)
    assert result.summary["reasons"]["missing_identity"] == 4
    sample = identity.samples[0].model_copy(update={"sample_id": "second-primary"})
    ambiguous = replace(
        identity,
        samples=identity.samples + (sample,),
        links=identity.links
        + (
            FileSampleLink(
                file_id=source.file_id, case_id=sample.case_id, sample_id=sample.sample_id
            ),
        ),
    )
    with pytest.raises(IdentityError, match="ambiguous_sample"):
        ambiguous.resolve(source.file_id)


def test_gene_normalization():
    result = normalize_gene("ENSG00000141510.18")
    assert result["gene_id"] == "ENSG00000141510"
    assert result["source_gene_id"] == "ENSG00000141510.18" and result["gene_version"] == "18"
    assert normalize_gene("ENSG00000141510.18_PAR_Y")["gene_id"].endswith("_PAR_Y")
    with pytest.raises(ValueError):
        normalize_gene("TP53")


def test_malformed_duplicate_and_bounded_rows(gdc_fixture, tmp_path):
    def expand(raw):
        lines = raw.splitlines()
        gene = next(line for line in lines if line.startswith(b"ENSG"))
        return b"\n".join(lines[:2] + [gene] * 10003 + [b"malformed"]) + b"\n"

    result = modified(gdc_fixture, tmp_path, expand, batch_size=17)
    assert result.summary["rows_accepted"] == 10003  # Source multiplicity is preserved.
    assert result.summary["rows_rejected"] == 1
    assert result.max_buffered_rows == 17
    assert pq.ParquetFile(result.parquet).metadata.num_rows == 10003


@pytest.mark.parametrize(
    "column,value",
    [("Start", "999999999"), ("Segment_Mean", "nan"), ("Start", "0"), ("Num_Probes", "-1")],
)
def test_segment_validation(gdc_fixture, tmp_path, column, value):
    def change(raw):
        lines = raw.decode().splitlines()
        header, row = lines[0].split("\t"), lines[1].split("\t")
        row[header.index(column)] = value
        return (lines[0] + "\n" + "\t".join(row) + "\n").encode()

    result = modified(gdc_fixture, tmp_path, change, name="segment.tsv")
    assert result.summary["rows_rejected"] == 1


def test_arbitrary_path_job_rejected():
    with pytest.raises(ValueError):
        MaterializationRequest.model_validate(
            {"source_path": "C:/anything", "modality": "mutation"}
        )


def test_inconsistent_frozen_links(gdc_fixture):
    _, _, identity = gdc_fixture("rna.tsv")
    with pytest.raises(IdentityError, match="inconsistent_frozen"):
        FrozenIdentityResolver(identity.cases, (), identity.aliquots, identity.links)


@pytest.mark.parametrize(
    "column,value",
    [
        ("Reference_Allele", "Z"),
        ("Tumor_Seq_Allele2", "?"),
        ("Start_Position", "0"),
        ("End_Position", "1"),
    ],
)
def test_mutation_validation(gdc_fixture, tmp_path, column, value):
    def change(raw):
        lines = [line for line in raw.decode().splitlines() if not line.startswith("#")]
        header, row = lines[0].split("\t"), lines[1].split("\t")
        row[header.index(column)] = value
        return (lines[0] + "\n" + "\t".join(row) + "\n").encode()

    result = modified(gdc_fixture, tmp_path, change, name="mutation.maf")
    assert result.summary["rows_rejected"] == 1


def test_aliquot_uuid_barcode_conflict_and_primary_exclusion(gdc_fixture):
    _, source, identity = gdc_fixture("mutation.maf")
    aliquot = next(
        a for a in identity.aliquots if a.aliquot_id == "3c6dcba5-1312-40ca-b589-07f7d88b3477"
    )
    others = [a for a in identity.aliquots if a.aliquot_id != aliquot.aliquot_id]
    assert others
    marked = others[0].model_copy(update={"submitter_id": "conflicting-barcode"})
    changed = replace(
        identity,
        aliquots=tuple(
            marked if a.aliquot_id == marked.aliquot_id else a for a in identity.aliquots
        ),
    )
    with pytest.raises(IdentityError, match="missing_identity"):
        changed.resolve(
            source.file_id, aliquot_id=aliquot.aliquot_id, submitter_id="conflicting-barcode"
        )
    normal = next(s for s in identity.samples if s.sample_type != "Primary Tumor")
    normal_aliquot = next(a for a in identity.aliquots if a.sample_id == normal.sample_id)
    with pytest.raises(IdentityError, match="not_primary_tumor"):
        identity.resolve(source.file_id, aliquot_id=normal_aliquot.aliquot_id)
    with pytest.raises(IdentityError, match="missing_identity"):
        identity.resolve(source.file_id, submitter_id="made-up-barcode")


def test_clinical_missing_data_and_multiple_diagnoses(tmp_path):
    from packages.schemas.identity import CaseRecord

    path = tmp_path / "clinical.json"
    path.write_text(
        json.dumps(
            {
                "data": {
                    "hits": [
                        {
                            "case_id": "c",
                            "diagnoses": [
                                {"diagnosis_id": "d1"},
                                {"diagnosis_id": "d2", "follow_ups": [{"days_to_follow_up": 12}]},
                            ],
                        }
                    ]
                }
            }
        )
    )
    result = materialize_verified(
        path,
        tmp_path / "out",
        source=None,
        expected_file_id=None,
        expected_sha256=sha256_file(str(path)),
        modality="clinical",
        identity=FrozenIdentityResolver(
            (CaseRecord(case_id="c", project_id="TCGA-LUAD"),), (), (), ()
        ),
    )
    rows = pq.read_table(result.parquet).to_pylist()
    assert len(rows) == 2
    assert all(r["days_to_death"] is None and r["days_to_last_follow_up"] is None for r in rows)
    assert json.loads(rows[1]["follow_ups_json"])[0]["days_to_follow_up"] == 12


def test_corrupt_gzip_has_no_output(gdc_fixture, tmp_path):
    with pytest.raises((EOFError, OSError)):
        modified(gdc_fixture, tmp_path, lambda b: gzip.compress(b, mtime=0)[:-10])
    assert not (tmp_path / "out" / "canonical.parquet").exists()


def test_parser_is_incremental_and_has_explicit_empty_input(gdc_fixture, tmp_path):
    from packages.gdc.parsers import Diagnostics, ParseContext

    path, source, identity = gdc_fixture("rna.tsv")
    parser = select_parser(
        modality="expression", version="1", source=source, measurement="unstranded"
    )
    diagnostics = Diagnostics()
    records = parser.records(
        ParseContext(path, source.file_id, sha256_file(str(path)), identity, "unstranded"),
        diagnostics,
    )
    next(records)
    assert diagnostics.rows_seen == 5 and diagnostics.rows_accepted == 1
    records.close()
    with pytest.raises(ValueError, match="missing_header"):
        modified(gdc_fixture, tmp_path, lambda b: b"")
