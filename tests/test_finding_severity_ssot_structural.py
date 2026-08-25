# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Structural guard for V031_SEVERITY_HARDCODE_ARCHITECTURAL_REMEDIATION.

Two consumers of ``codes.py``'s ``CODE_DEFINITIONS`` (the declared single
source of truth for finding severity) were found this session to bypass it
with a hardcoded literal instead: Z301 (in ``scanner.py``'s reference
pipeline, fixed via its own ``is_warning`` field) and Z406/Z503 (in
``_check.py``, fixed by routing through ``_finding_severity()``). A visual
sweep found Z406/Z503 wrong among 7 hardcoded-literal sites; this test
exists so the *next* one is caught by CI, not by a docs-hygiene audit
months later.

This test parses ``_check.py``'s AST directly (not by importing and
introspecting bytecode) and asserts that no ``Finding(...)`` call site
passes a bare string literal (``"error"``, ``"warning"``, ``"info"``, ...)
as its ``severity=`` keyword argument. Accepted patterns are a call
(``_finding_severity(code)``), an attribute access (``rule_f.severity`` --
derived from an object set elsewhere), or a conditional expression whose
branches are selected by a dynamic condition (``"warning" if
ref_f.is_warning else "error"`` -- the reference-pipeline's own SSoT-derived
field, not a fixed-per-code literal). A bare ``ast.Constant`` string is the
one pattern this test forbids.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_PY_PATH = REPO_ROOT / "src" / "zenzic" / "cli" / "_check.py"


def _is_bare_string_literal(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _find_finding_severity_hardcodes() -> list[str]:
    """Return a list of "line N: severity='...'" violations, if any."""
    tree = ast.parse(CHECK_PY_PATH.read_text(encoding="utf-8"), filename=str(CHECK_PY_PATH))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "Finding":
            continue

        for kw in node.keywords:
            if kw.arg != "severity":
                continue
            if _is_bare_string_literal(kw.value):
                violations.append(
                    f"line {node.lineno}: Finding(..., severity={ast.dump(kw.value)}) "
                    f"is a bare string literal -- must derive from codes.py via "
                    f"_finding_severity(code) or an equivalent dynamic source."
                )

    return violations


def test_no_hardcoded_severity_literals_in_check_py() -> None:
    """No Finding(...) call site in _check.py may hardcode its severity=
    as a bare string literal -- it must be derived from codes.py's
    CODE_DEFINITIONS (the SSoT), directly or indirectly.

    This test is proven to catch the bug class it guards against: reverted
    against the pre-fix state of this file (Z406/Z503 hardcoded as
    severity="error"), it fails with exactly those two violations. See
    V031_SEVERITY_HARDCODE_ARCHITECTURAL_REMEDIATION for the verification
    transcript.
    """
    violations = _find_finding_severity_hardcodes()
    assert not violations, (
        "Hardcoded severity literal(s) found in _check.py's Finding(...) "
        "construction -- this is the exact bug shape already found twice "
        "this session (Z406, Z503). Route through _finding_severity(code) "
        "instead:\n" + "\n".join(violations)
    )
