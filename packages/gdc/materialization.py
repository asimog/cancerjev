"""Verified-payload API, independent of jobs and database persistence."""

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import UnionType
from typing import Annotated, Union, get_args, get_origin

import pyarrow as pa
import pyarrow.parquet as pq

from packages.gdc.identity import SELECTION_VERSION, FrozenIdentityResolver
from packages.gdc.parsers import Diagnostics, ParseContext, canonical_json, select_parser
from packages.gdc.selection import select_primary_tumor
from packages.gdc.transfer import verify_file
from packages.provenance.hashing import sha256_file
from packages.schemas.snapshot import SnapshotObject


def arrow_schema(model) -> pa.Schema:
    def scalar(annotation):
        if get_origin(annotation) is Annotated:
            return scalar(get_args(annotation)[0])
        if get_origin(annotation) in (Union, UnionType):
            return scalar(next(v for v in get_args(annotation) if v is not type(None)))
        return {str: pa.string(), int: pa.int64(), float: pa.float64(), bool: pa.bool_()}[
            annotation
        ]

    return pa.schema(
        [
            pa.field(
                name, scalar(field.annotation), nullable=type(None) in get_args(field.annotation)
            )
            for name, field in model.model_fields.items()
        ]
    )


@dataclass(frozen=True)
class Materialized:
    parquet: Path
    diagnostics: Path
    physical_sha256: str
    logical_sha256: str
    summary: dict
    max_buffered_rows: int
    parser_name: str
    parser_version: str
    schema_version: str


def materialize_verified(
    source_path: Path,
    output_dir: Path,
    *,
    source: SnapshotObject | None,
    expected_file_id: str | None,
    expected_sha256: str,
    identity: FrozenIdentityResolver,
    modality: str,
    parser_version: str = "1",
    measurement: str = "",
    batch_size: int = 4096,
) -> Materialized:
    if not 1 <= batch_size <= 65536:
        raise ValueError("batch_size must be between 1 and 65536")
    if source is not None:
        if source.file_id != expected_file_id or source.access != "open":
            raise ValueError("source_file_association_mismatch")
    elif expected_file_id is not None or modality != "clinical":
        raise ValueError("missing_frozen_source_metadata")
    parser = select_parser(
        modality=modality, version=parser_version, source=source, measurement=measurement
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output, rejects = output_dir / "canonical.parquet", output_dir / "diagnostics.jsonl"
    schema = arrow_schema(parser.model)
    logical = hashlib.sha256()
    logical.update(
        (
            canonical_json(
                {
                    "encoding": "canonical-json-lines-v1",
                    "schema": parser.model.__name__,
                    "schema_version": parser.schema_version,
                }
            )
            + "\n"
        ).encode()
    )
    maximum = 0
    # A private verified copy prevents the caller changing bytes between verification and parsing.
    with tempfile.TemporaryDirectory(prefix="cancerjev-verified-") as staging:
        staged = Path(staging) / "source"
        shutil.copyfile(source_path, staged)
        if sha256_file(str(staged)) != expected_sha256:
            raise ValueError("source_SHA256_mismatch")
        if source:
            verify_file(staged, source.md5sum, source.file_size)
        context = ParseContext(
            staged, expected_file_id or "", expected_sha256, identity, measurement
        )
        try:
            with (
                rejects.open("w", encoding="utf-8", newline="\n") as log,
                pq.ParquetWriter(
                    output,
                    schema,
                    compression="zstd",
                    compression_level=3,
                    version="2.6",
                    use_dictionary=False,
                    write_statistics=True,
                ) as writer,
            ):
                diagnostics = Diagnostics(
                    emit=lambda value: log.write(canonical_json(value) + "\n")
                )
                file_samples = {
                    link.sample_id for link in identity.links if link.file_id == expected_file_id
                }
                if source:
                    for sample_id, reason in select_primary_tumor(list(identity.samples)).excluded:
                        if sample_id in file_samples:
                            diagnostics.samples_excluded += 1
                            diagnostics.emit(
                                {
                                    "scope": "sample",
                                    "sample_id": sample_id,
                                    "reason": reason,
                                    "policy_version": SELECTION_VERSION,
                                }
                            )
                batch = []
                for record in parser.records(context, diagnostics):
                    row = record.model_dump(mode="json")
                    logical.update((canonical_json(row) + "\n").encode("utf-8"))
                    batch.append(row)
                    maximum = max(maximum, len(batch))
                    if len(batch) == batch_size:
                        writer.write_table(pa.Table.from_pylist(batch, schema=schema))
                        batch.clear()
                if batch:
                    writer.write_table(pa.Table.from_pylist(batch, schema=schema))
                log.write(json.dumps({"summary": diagnostics.summary()}, sort_keys=True) + "\n")
        except Exception:
            output.unlink(missing_ok=True)
            rejects.unlink(missing_ok=True)
            raise
    return Materialized(
        output,
        rejects,
        sha256_file(str(output)),
        "sha256:" + logical.hexdigest(),
        diagnostics.summary(),
        maximum,
        parser.name,
        parser.version,
        parser.schema_version,
    )
