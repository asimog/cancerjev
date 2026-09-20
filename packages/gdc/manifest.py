import csv
import io

from packages.gdc.policy import require_open
from packages.schemas.identity import FileRecord


def generate_manifest(files: list[FileRecord]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(["id", "filename", "md5", "size", "state"])
    for item in sorted(files, key=lambda value: value.file_id):
        require_open(item.access)
        writer.writerow(
            [item.file_id, item.file_name, item.md5sum.lower(), item.file_size, "released"]
        )
    return output.getvalue().encode()


def validate_manifest(raw: bytes, files) -> None:
    """Live metadata must not replace the frozen download identity."""
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8")), delimiter="\t"))
    expected = {f.file_id: f for f in files}
    if len(rows) != len(expected) or {r.get("id") for r in rows} != set(expected):
        raise ValueError("GDC manifest membership differs from frozen snapshot")
    for row in rows:
        item = expected[row["id"]]
        if (
            row.get("filename") != item.file_name
            or row.get("md5", "").lower() != item.md5sum.lower()
            or row.get("size") != str(item.file_size)
            # GDC manifests report storage state "validated" for current released files.
            or row.get("state") not in {"validated", "released"}
        ):
            raise ValueError("GDC manifest metadata differs from frozen snapshot")
