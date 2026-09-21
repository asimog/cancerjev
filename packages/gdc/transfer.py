"""Quarantined GDC Data Transfer Tool boundary.

CJ-R00 containment decision: the complete-file download wrapper is removed
because it could transfer a complete BAM with no metadata-first plan, size
bound, or BAM denial. Production acquisition registers already-acquired
bytes through the trusted source boundary (`MaterializationService`),
which verifies frozen snapshot metadata, checksums, and sizes. The full
metadata-first acquisition planner and bounded slicing arrive with CJ-R04.

The capability probe remains so R04 can verify the official binary, and
`verify_file` remains the checksum/size authority for registered bytes.
"""

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class GDCClientUnavailable(RuntimeError):
    pass


class ChecksumMismatch(RuntimeError):
    pass


@dataclass(frozen=True)
class TransferResult:
    file_id: str
    path: Path
    md5: str
    sha256: str
    size: int


class GDCTransfer:
    """Official-binary capability probe only; no download path exists."""

    def __init__(self, binary: str = "gdc-client"):
        self.binary = binary

    def capability(self) -> str:
        path = shutil.which(self.binary)
        if not path:
            raise GDCClientUnavailable(f"official gdc-client unavailable: {self.binary}")
        result = subprocess.run(
            [path, "--version"], capture_output=True, text=True, check=False, timeout=15
        )
        if result.returncode:
            raise GDCClientUnavailable(result.stderr.strip() or "version check failed")
        return result.stdout.strip() or result.stderr.strip()


def verify_file(path: Path, expected_md5: str, expected_size: int | None = None) -> TransferResult:
    md5, sha = hashlib.md5(usedforsecurity=False), hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            md5.update(chunk)
            sha.update(chunk)
    if md5.hexdigest().lower() != expected_md5.lower() or (
        expected_size is not None and size != expected_size
    ):
        raise ChecksumMismatch(f"checksum/size mismatch for {path.name}")
    return TransferResult(path.parent.name, path, md5.hexdigest(), sha.hexdigest(), size)
