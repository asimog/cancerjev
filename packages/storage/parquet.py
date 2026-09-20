from pathlib import Path

import duckdb
import polars as pl
from pydantic import BaseModel

from packages.provenance.hashing import sha256_file


def write_records(records: list[BaseModel] | list[dict], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [r.model_dump(mode="json") if isinstance(r, BaseModel) else r for r in records]
    pl.DataFrame(rows).write_parquet(path, compression="zstd", statistics=True)
    return sha256_file(str(path))


def query(path: Path, sql: str = "SELECT * FROM data") -> pl.DataFrame:
    with duckdb.connect() as db:
        db.execute("CREATE VIEW data AS SELECT * FROM read_parquet(?)", [str(path.resolve())])
        return db.execute(sql).pl()
