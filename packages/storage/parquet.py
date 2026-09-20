from pathlib import Path
from types import UnionType
from typing import Literal, Union, get_args, get_origin

import duckdb
import polars as pl
from pydantic import BaseModel

from packages.provenance.hashing import sha256_file


def _polars_type(annotation: object) -> pl.DataType:
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        values = [value for value in get_args(annotation) if value is not type(None)]
        return _polars_type(values[0])
    if origin is Literal:
        return _polars_type(type(get_args(annotation)[0]))
    return {str: pl.String, int: pl.Int64, float: pl.Float64, bool: pl.Boolean}.get(
        annotation, pl.String
    )


def write_records(
    records: list[BaseModel] | list[dict], path: Path, *, model: type[BaseModel] | None = None
) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [r.model_dump(mode="json") if isinstance(r, BaseModel) else r for r in records]
    inferred_model = type(records[0]) if records and isinstance(records[0], BaseModel) else None
    record_model = model or inferred_model
    schema = (
        {name: _polars_type(field.annotation) for name, field in record_model.model_fields.items()}
        if record_model
        else None
    )
    if not rows and schema is None:
        raise ValueError("empty record sets require an explicit model schema")
    pl.DataFrame(rows, schema=schema, strict=False).write_parquet(
        path, compression="zstd", statistics=True
    )
    return sha256_file(str(path))


def query(path: Path, sql: str = "SELECT * FROM data") -> pl.DataFrame:
    with duckdb.connect() as db:
        db.read_parquet(str(path.resolve())).create_view("data")
        return db.execute(sql).pl()


def read_records(path: Path, model: type[BaseModel]) -> list[BaseModel]:
    """Read typed records from a Parquet file using a Pydantic model."""
    import pyarrow.parquet as pq
    records = []
    for batch in pq.ParquetFile(path).iter_batches(batch_size=4096):
        for row in batch.to_pylist():
            records.append(model.model_validate(row))
    return records
