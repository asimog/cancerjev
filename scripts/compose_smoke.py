"""Check a running Compose data plane and cross-service MinIO CAS visibility."""

import argparse
import json
import shutil
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ("api", "ingest-worker", "statistics-worker")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("docker must be on PATH")
    command = [docker, "compose", "-p", args.project]

    def execute(service: str, code: str) -> str:
        try:
            return subprocess.run(
                [*command, "exec", "-T", service, "python", "-"],
                input=code,
                text=True,
                capture_output=True,
                check=True,
                cwd=ROOT,
                timeout=60,
            ).stdout.strip()
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"{service} smoke failed: {exc.stderr}") from exc

    config = json.loads(
        subprocess.run(
            [*command, "config", "--format", "json"],
            capture_output=True,
            text=True,
            check=True,
            cwd=ROOT,
            timeout=30,
        ).stdout
    )
    expected = {
        "CANCERJEV_OBJECT_BACKEND": "s3",
        "CANCERJEV_OBJECT_BUCKET": "cancerjev",
        "CANCERJEV_OBJECT_ENDPOINT_URL": "http://minio:9000",
    }
    for service in SERVICES:
        environment = config["services"][service]["environment"]
        assert all(environment.get(key) == value for key, value in expected.items())
        assert "CANCERJEV_S3_ENDPOINT" not in environment

    # Independent service processes construct the store from their actual runtime environment.
    objects = {}
    run_id = uuid.uuid4().hex
    for writer in SERVICES:
        payload = f"CancerJev PR09 shared CAS smoke: {run_id}:{writer}"
        digest = execute(
            writer,
            f"""
from packages.storage.config import StorageSettings
settings = StorageSettings()
assert settings.object_backend == 's3' and settings.object_bucket == 'cancerjev'
print(settings.store().put({payload!r}.encode()))
""",
        )
        objects[digest] = payload
    for reader in SERVICES:
        execute(
            reader,
            f"""
import tempfile
from pathlib import Path
from packages.storage.config import StorageSettings
store = StorageSettings().store()
with tempfile.TemporaryDirectory() as tmp:
    for digest, payload in {objects!r}.items():
        path = Path(tmp) / digest.removeprefix('sha256:')
        store.stage(digest, path)
        assert path.read_bytes() == payload.encode()
print('verified')
""",
        )
    execute(
        "api",
        """
import urllib.request
from sqlalchemy import text
from packages.database.session import session_factory
from packages.database.config import resolve_database_url
with session_factory(resolve_database_url())() as session:
    assert session.scalar(text('SELECT version_num FROM alembic_version')) == '0005'
for url in ('http://localhost:8000/health', 'http://web:3000/health'):
    with urllib.request.urlopen(url, timeout=20) as response:
        assert response.status == 200
print('healthy')
""",
    )
    for service in ("api", "web", "postgres", "minio"):
        container = subprocess.run(
            [*command, "ps", "-q", service],
            text=True,
            capture_output=True,
            check=True,
            cwd=ROOT,
            timeout=30,
        ).stdout.strip()
        health = subprocess.run(
            [docker, "inspect", "--format", "{{.State.Health.Status}}", container],
            text=True,
            capture_output=True,
            check=True,
            timeout=30,
        ).stdout.strip()
        assert health == "healthy", f"{service} healthcheck: {health}"
    print("PASS: API/web health, migration 0005, and all 9 cross-service MinIO CAS reads")


if __name__ == "__main__":
    main()
