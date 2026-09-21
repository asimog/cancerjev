"""Distribution contract: the wheel must contain the complete runtime code.

The source tree and Docker image mask packaging omissions because both make
every top-level package importable through the working directory. These tests
build the real wheel and import from it outside the checkout so a missing
package cannot hide behind an editable install or a copied layout.
"""

import os
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_PACKAGES = ("apps", "packages", "scientific", "workers")
WHEEL_IMPORTS = (
    "apps.api.main",
    "workers.ingest.__main__",
    "workers.statistics.__main__",
    "scientific.crossmodal",
)


def test_wheel_configuration_covers_every_runtime_package() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    packaged = set(config["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"])
    assert packaged == set(RUNTIME_PACKAGES)


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory) -> Path:
    try:
        import build  # noqa: F401
    except ImportError:
        pytest.skip("build package is not installed")
    out = tmp_path_factory.mktemp("wheel")
    try:
        subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(out)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=600,
            check=True,
        )
    except subprocess.CalledProcessError:
        # Offline environments may still build against a locally installed backend.
        subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--no-isolation",
                "--outdir",
                str(out),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=600,
            check=True,
        )
    wheels = list(out.glob("*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def test_wheel_record_contains_runtime_packages(built_wheel: Path) -> None:
    with zipfile.ZipFile(built_wheel) as wheel:
        record = next(name for name in wheel.namelist() if name.endswith(".dist-info/RECORD"))
        files = {line.split(",")[0] for line in wheel.read(record).decode().splitlines()}
    for package in RUNTIME_PACKAGES:
        assert (ROOT / package).is_dir()
        assert any(
            path.startswith(package + "/") and path.endswith(".py") for path in files
        ), f"wheel omits runtime package: {package}"


def test_wheel_imports_outside_the_source_tree(built_wheel: Path, tmp_path: Path) -> None:
    installed = tmp_path / "wheel-contents"
    with zipfile.ZipFile(built_wheel) as wheel:
        wheel.extractall(installed)
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(installed)!r})\n"
        + "".join(f"import {module}\n" for module in WHEEL_IMPORTS)
        + "\n".join(
            f"assert sys.modules[{module!r}].__file__.startswith({str(installed)!r}), ("
            f"{module!r}, sys.modules[{module!r}].__file__)"
            for module in WHEEL_IMPORTS + ("apps", "packages", "workers")
        )
        + "\nprint('verified')\n"
    )
    # Run from outside the checkout with no PYTHONPATH so an editable install
    # or the source tree cannot satisfy the import in place of the wheel.
    environment = {key: value for key, value in os.environ.items()}
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("verified")
