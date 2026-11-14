"""Scope guard for the standalone qbacktest package.

The qbacktest modules are parsed with :mod:`ast` rather than imported or
executed, so this test can inspect their import surface without side effects.
The forbidden roots are exactly the ones guarded by the qresearch scope test.
"""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QBACKTEST_ROOT = PROJECT_ROOT / "qbacktest"

FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "mdl",
        "ollama",
        "openai",
        "anthropic",
        "httpx",
        "requests",
        "urllib",
        "socket",
        "http",
        "torch",
        "tensorflow",
        "keras",
        "sklearn",
        "pandas",
        "transformers",
        "peft",
        "trl",
        "bitsandbytes",
    }
)


def _import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # Relative imports stay inside the qbacktest package.
                roots.add("qbacktest")
            elif node.module:
                roots.add(node.module.split(".", 1)[0])
    return roots


def test_qbacktest_has_no_forbidden_import_roots() -> None:
    files = sorted(QBACKTEST_ROOT.rglob("*.py"))
    assert files, f"no Python files found under {QBACKTEST_ROOT}"

    violations: list[str] = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        assert source.strip(), f"{path.relative_to(PROJECT_ROOT)} is empty"
        for root in sorted(_import_roots(path)):
            if root in FORBIDDEN_IMPORT_ROOTS:
                relative = path.relative_to(PROJECT_ROOT)
                violations.append(
                    f"{relative}: forbidden import root {root!r}"
                )

    assert not violations, "qbacktest imports forbidden modules:\n" + "\n".join(
        violations
    )


def test_qbacktest_does_not_import_mdl() -> None:
    files = sorted(QBACKTEST_ROOT.rglob("*.py"))
    assert files

    for path in files:
        roots = _import_roots(path)
        assert "mdl" not in roots
