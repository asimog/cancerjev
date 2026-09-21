"""Import-boundary contract: statistics leaves stay decoupled from engines.

A past regression eagerly imported the engine registry from
``packages.statistics.__init__`` while the scientific engine imported the
statistics leaf primitives, creating a cycle that only manifested when the
scientific engine was imported first. Each check runs in a fresh interpreter
with the repository root as the only path source, proving import order can
never re-enter a partially initialized module.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def import_isolated(code: str) -> None:
    environment = {key: value for key, value in os.environ.items()}
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        env=environment,
    )
    assert result.returncode == 0, result.stderr


def test_scientific_engine_imports_first_without_cycle() -> None:
    import_isolated(
        "import scientific.crossmodal\n"
        "from scientific.crossmodal import EngineContext, analyze_cnv_rna\n"
        "import packages.statistics.registry\n"
    )


def test_statistics_leaves_do_not_initialize_engines_or_registry() -> None:
    import_isolated(
        "import packages.statistics.core, packages.statistics.crossmodal\n"
        "import sys\n"
        "assert 'packages.statistics.registry' not in sys.modules\n"
        "assert 'scientific.crossmodal' not in sys.modules\n"
    )


def test_registry_resolves_the_r00_engine() -> None:
    import_isolated(
        "from packages.statistics.registry import ENGINES, resolve_engine\n"
        "spec = resolve_engine('cnv_rna', '1')\n"
        "assert spec.modalities == ('cnv', 'expression')\n"
        "try:\n"
        "    resolve_engine('cnv_rna', '9')\n"
        "    raise SystemExit('unsupported version must fail')\n"
        "except ValueError:\n"
        "    pass\n"
        "assert set(ENGINES) == {'cnv_rna'}\n"
    )
