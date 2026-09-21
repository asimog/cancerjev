"""Open-data surface contract: no GDC credential or complete-BAM path exists.

The AST scanner distinguishes prohibited executable token paths from
documentation and docstrings that describe the prohibition, and it is tested
against its own positive and negative fixtures so it can neither silently
bypass nor permanently false-positive. The runtime checks prove authorization
responses map to terminal UNAVAILABLE_ACCESS with no authenticated retry and
that the complete-file transfer path is quarantined.
"""

import ast
import re
from pathlib import Path

import pytest
import respx

from packages.gdc.client import GDCClient
from packages.gdc.policy import UNAVAILABLE_ACCESS, GDCUnavailableAccess
from packages.gdc.transfer import GDCTransfer

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("packages", "workers", "apps", "scientific", "migrations", "scripts")
BASE = "https://api.gdc.cancer.gov"

#: Prohibited credential-shaped literals in executable code (docstrings excluded).
DENIED_LITERAL = re.compile(
    r"(?i)\b(?:x-auth-token|dbgap|gdc[_-]?token|gdc[_-]?api[_-]?key|token[_-]?file)\b"
)
#: Prohibited GDC/dbGaP credential-shaped environment variable names.
DENIED_ENV_NAME = re.compile(
    r"(?i)^(?:gdc|dbgap)[_-].*(?:token|key|secret|password|credential)s?$"
)
#: Subprocess arguments that would invoke complete download or token auth.
DENIED_SUBPROCESS_ARG = {"download", "--token"}
#: Keyword arguments that would attach credentials to an HTTP client/request.
DENIED_KEYWORDS = {"auth", "cookies"}
#: Exact executable-code literal mentions that are themselves security controls.
ALLOWED_MENTIONS = {
    ("packages/gdc/client.py", "x-auth-token"): "runtime header-rejection denylist",
}


def _docstring_positions(tree: ast.Module) -> set[tuple[int, int]]:
    positions: set[tuple[int, int]] = set()

    def visit_body(body: list[ast.stmt]) -> None:
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            positions.add((body[0].value.lineno, body[0].value.col_offset))

    visit_body(tree.body)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            visit_body(node.body)
    return positions


def _environment_name(node: ast.AST) -> str | None:
    """Return the constant environment name an os.environ access reads, if any."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "environ"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ):
        return str(node.args[0].value)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getenv"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ):
        return str(node.args[0].value)
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "environ"
        and isinstance(node.slice, ast.Constant)
    ):
        return str(node.slice.value)
    return None


def _subprocess_arguments(node: ast.Call) -> list[str]:
    constants: list[str] = []
    for argument in node.args:
        if isinstance(argument, ast.List | ast.Tuple):
            constants.extend(
                element.value for element in argument.elts if isinstance(element, ast.Constant)
            )
    return constants


def scan_sources(sources: dict[str, str]) -> list[str]:
    """Flag prohibited credential/transfer surfaces in parsed production code."""
    violations: list[str] = []
    for path, source in sources.items():
        try:
            tree = ast.parse(source)
        except SyntaxError:
            violations.append(f"{path}: source is not parsable")
            continue
        docstrings = _docstring_positions(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if (node.lineno, node.col_offset) in docstrings:
                    continue
                for match in DENIED_LITERAL.finditer(node.value):
                    matched = match.group(0).lower()
                    if (path, matched) not in ALLOWED_MENTIONS:
                        violations.append(f"{path}:{node.lineno}: denied literal {matched!r}")
            name = _environment_name(node)
            if name is not None and DENIED_ENV_NAME.match(name):
                violations.append(f"{path}:{node.lineno}: denied environment read {name!r}")
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg in DENIED_KEYWORDS:
                        violations.append(
                            f"{path}:{node.lineno}: credential keyword {keyword.arg!r}"
                        )
                if isinstance(node.func, ast.Attribute) and node.func.attr in {
                    "run",
                    "Popen",
                    "check_output",
                    "check_call",
                }:
                    for argument in _subprocess_arguments(node):
                        if argument in DENIED_SUBPROCESS_ARG:
                            violations.append(
                                f"{path}:{node.lineno}: denied subprocess argument"
                                f" {argument!r}"
                            )
    return violations


def test_scanner_flags_prohibited_surfaces_and_passes_documentation() -> None:
    violations = scan_sources(
        {
            "packages/gdc/evil_env.py": "import os\nTOKEN = os.getenv('GDC_TOKEN')\n",
            "packages/gdc/evil_environ.py": "import os\nX = os.environ['DBGAP_SECRET']\n",
            "packages/gdc/evil_literal.py": 'HEADER = "X-Auth-Token"\n',
            "packages/gdc/evil_kwarg.py": "import httpx\nhttpx.AsyncClient(auth='bearer')\n",
            "packages/gdc/evil_subprocess.py": (
                "import subprocess\nsubprocess.run(['gdc-client', 'download', '-m', 'x'])\n"
            ),
            "packages/gdc/policy_doc.py": (
                '"""X-Auth-Token, dbGaP credentials, GDC tokens, and token files are'
                ' prohibited."""\n'
            ),
        }
    )
    joined = "\n".join(violations).lower()
    assert "gdc_token" in joined
    assert "dbgap_secret" in joined
    assert "x-auth-token" in joined
    assert "credential keyword 'auth'" in joined
    assert "denied subprocess argument 'download'" in joined
    assert "policy_doc.py" not in joined  # documentation is never a violation


def test_scanner_allows_only_the_documented_security_control() -> None:
    violations = scan_sources(
        {
            "packages/gdc/client.py": 'REJECT = ("x-auth-token", "authorization", "cookie")\n',
            "packages/gdc/other.py": 'SUSPECT = "x-auth-token"\n',
        }
    )
    assert [line for line in violations if "client.py" in line] == []
    assert any("other.py" in line for line in violations)


def production_sources() -> dict[str, str]:
    sources: dict[str, str] = {}
    for root in PRODUCTION_ROOTS:
        for path in (ROOT / root).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            sources[path.relative_to(ROOT).as_posix()] = path.read_text(encoding="utf-8")
    assert len(sources) > 40  # the scan covers the real production tree
    return sources


def test_production_code_has_no_gdc_credential_or_download_surface() -> None:
    assert scan_sources(production_sources()) == []


def test_complete_file_transfer_is_quarantined() -> None:
    assert not hasattr(GDCTransfer, "download")
    # No production subprocess invocation requests a complete download or token.
    assert not [line for line in scan_sources(production_sources()) if "download" in line]


def test_unavailable_access_is_a_bounded_job_failure_reason() -> None:
    from packages.database.jobs import FAILURE_REASONS

    assert UNAVAILABLE_ACCESS in FAILURE_REASONS


@pytest.mark.parametrize("status", [401, 403])
@respx.mock
async def test_authorization_failures_map_to_terminal_unavailable_access(status: int) -> None:
    respx.get(BASE + "/status").respond(status)
    async with GDCClient(BASE, max_retries=4) as client:
        with pytest.raises(GDCUnavailableAccess) as excinfo:
            await client.status()
    assert excinfo.value.retryable is False
    assert excinfo.value.failure_reason == UNAVAILABLE_ACCESS
    # A terminal access failure is never retried, authenticated or otherwise.
    assert len(respx.calls) == 1
