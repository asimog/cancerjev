import csv
from pathlib import Path

from packages.schemas.molecular import (
    ClinicalRecord,
    CNVRecord,
    ExpressionRecord,
    MutationRecord,
    SegmentCNVRecord,
)
from packages.storage.objects import FileObjectStore
from packages.storage.parquet import write_records

SCHEMAS = {
    "mutation": MutationRecord,
    "expression": ExpressionRecord,
    "cnv": CNVRecord,
    "segment_cnv": SegmentCNVRecord,
    "clinical": ClinicalRecord,
}


def materialize_delimited(
    source: Path, destination: Path, modality: str, *, delimiter: str = "\t"
) -> str:
    """Stream a normalized delimited file through strict canonical records to Parquet."""
    schema = SCHEMAS.get(modality)
    if schema is None:
        raise ValueError(f"unsupported modality: {modality}")
    with source.open(encoding="utf-8", newline="") as stream:
        records = [
            schema.model_validate(row) for row in csv.DictReader(stream, delimiter=delimiter)
        ]
    return write_records(records, destination)


def materialize_snapshot(payload: dict) -> dict:
    source = Path(payload["source_path"]).resolve()
    output = Path(payload["output_path"]).resolve()
    cache_root = Path(payload.get("allowed_root", ".data")).resolve()
    if cache_root not in source.parents or cache_root not in output.parents:
        raise ValueError("materialization path outside configured root")
    digest = materialize_delimited(source, output, payload["modality"])
    store = FileObjectStore(Path(payload.get("object_root", cache_root / "objects")))
    object_digest = store.put_file(output, digest)
    return {
        "modality": payload["modality"],
        "parquet_sha256": object_digest,
        "rows_path": str(output),
    }
