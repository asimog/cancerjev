from pathlib import Path

import pytest

from packages.gdc.coverage import build_coverage
from packages.gdc.manifest import generate_manifest
from packages.gdc.selection import select_primary_tumor
from packages.gdc.transfer import ChecksumMismatch, verify_file
from packages.schemas.identity import CaseRecord, FileRecord, FileSampleLink, SampleRecord
from packages.statistics import benjamini_hochberg, cnv_expression
from packages.storage.objects import FileObjectStore, object_key


def file(**overrides):
    values = {
        "file_id": "f1",
        "file_name": "x.tsv",
        "file_size": 3,
        "md5sum": "a" * 32,
        "access": "open",
        "data_category": "Transcriptome Profiling",
        "data_type": "Gene Expression Quantification",
    }
    return FileRecord(**(values | overrides))


def test_manifest_is_sorted_and_open() -> None:
    assert (
        generate_manifest([file(file_id="b"), file(file_id="a")]).splitlines()[1].startswith(b"a\t")
    )


def test_primary_selection_retains_ties_and_records_exclusion() -> None:
    samples = [
        SampleRecord(sample_id="b", case_id="c", sample_type="Primary Tumor"),
        SampleRecord(sample_id="a", case_id="c", sample_type="Primary Tumor"),
        SampleRecord(sample_id="n", case_id="c", sample_type="Solid Tissue Normal"),
    ]
    selected = select_primary_tumor(samples)
    assert [s.sample_id for s in selected.selected] == ["a", "b"]
    assert selected.excluded == (("n", "not_primary_tumor"),)


def test_case_coverage_does_not_infer_modalities() -> None:
    cases = [CaseRecord(case_id="c", project_id="TCGA-X")]
    result = build_coverage(cases, [file()], [FileSampleLink(file_id="f1", case_id="c")])[0]
    assert result.rna and not result.cnv and not result.mutation and not result.clinical


def test_bh_known_values_and_association() -> None:
    assert benjamini_hochberg([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.04, 0.04])
    result = cnv_expression([-2, -1, 1, 2], [-4, -2, 2, 4])
    assert result.effect_size == pytest.approx(1.0)


def test_content_store_and_checksum(tmp_path: Path) -> None:
    store = FileObjectStore(tmp_path / "objects")
    digest = store.put(b"abc")
    assert object_key(digest).endswith(digest.removeprefix("sha256:")) and store.verify(digest)
    source = tmp_path / "x"
    source.write_bytes(b"abc")
    assert verify_file(source, "900150983cd24fb0d6963f7d28e17f72", 3).sha256 == digest.split(":")[1]
    with pytest.raises(ChecksumMismatch):
        verify_file(source, "0" * 32)
