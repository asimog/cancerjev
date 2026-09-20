import csv
import io

from packages.schemas.identity import FileRecord


def generate_manifest(files: list[FileRecord]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(["id", "filename", "md5", "size", "state"])
    for item in sorted(files, key=lambda value: value.file_id):
        if item.access != "open":
            raise ValueError("controlled file cannot enter manifest")
        writer.writerow(
            [item.file_id, item.file_name, item.md5sum.lower(), item.file_size, "released"]
        )
    return output.getvalue().encode()
