"""Safe wrapper around the official GDC Data Transfer Tool."""

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

    def download(self, manifest: Path, destination: Path) -> subprocess.CompletedProcess[str]:
        manifest, destination = manifest.resolve(), destination.resolve()
        if not manifest.is_file():
            raise FileNotFoundError(manifest)
        destination.mkdir(parents=True, exist_ok=True)
        # Argument vector is deliberate: never use a shell or interpolate manifest content.
        result = subprocess.run(
            [self.binary, "download", "--resume", "-m", str(manifest), "-d", str(destination)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(f"gdc-client failed ({result.returncode}): {result.stderr}")
        return result


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
