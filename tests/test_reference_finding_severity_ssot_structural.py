# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Structural guard for V031_CODE_BACKLOG_BATCH3 Phase 2.

Mirrors the four existing structural guards (_check.py, rules.py,
incremental.py, scanner.py's RuleFinding construction) for scanner.py's
ReferenceFinding construction sites (Z301/Z302/Z303) -- the fifth confirmed
instance this session of the "hardcoded literal bypasses codes.py" bug
shape, this time on ReferenceFinding.is_warning rather than a severity=
string. Currently correct by coincidence (Z301/Z302/Z303 are all
"warning" in codes.py today) but structurally unguarded before this test:
test_scanner_severity_ssot_structural.py explicitly scopes itself to
RuleFinding(...)/_RF(...) call sites only and does not cover
ReferenceFinding(...) at all.

This test parses scanner.py's AST directly and asserts that no
ReferenceFinding(...) call site passes a bare boolean literal as its
is_warning= keyword argument.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCANNER_PY_PATH = REPO_ROOT / "src" / "zenzic" / "core" / "scanner.py"


def _is_bare_bool_literal(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, bool)


def _find_reference_finding_hardcodes() -> list[str]:
    """Return a list of "line N: is_warning=..." violations, if any."""
    tree = ast.parse(SCANNER_PY_PATH.read_text(encoding="utf-8"), filename=str(SCANNER_PY_PATH))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "ReferenceFinding":
            continue

        for kw in node.keywords:
            if kw.arg != "is_warning":
                continue
            value = kw.value
            if _is_bare_bool_literal(value) and isinstance(value, ast.Constant):
                violations.append(
                    f"line {value.lineno}: ReferenceFinding(..., is_warning={value.value!r}) "
                    f"is a bare boolean literal -- must derive from codes.py via "
                    f"code_severity(issue) == 'warning' or an equivalent dynamic source."
                )

    return violations


def test_no_hardcoded_is_warning_literals_in_scanner_py() -> None:
    """No ReferenceFinding(...) call site in scanner.py may hardcode its
    is_warning= as a bare boolean literal for a fixed code -- it must be
    derived from codes.py's CODE_DEFINITIONS (the SSoT) via code_severity(),
    directly or indirectly.

    This test is proven to catch the bug class it guards against: run
    against the pre-fix state (V031_CODE_BACKLOG_BATCH3), it fails with
    3 violations -- Z301, Z302, Z303, all hardcoded is_warning=True.
    Currently correct by coincidence (all 3 are "warning" in codes.py
    today), which is exactly why this guard matters: nothing previously
    caught a future drift the way the sibling RuleFinding/Finding guards
    already do for their own subsystems.
    """
    violations = _find_reference_finding_hardcodes()
    assert not violations, (
        "Hardcoded is_warning literal(s) found in scanner.py's "
        "ReferenceFinding(...) construction -- the fifth confirmed instance "
        "of the same bug shape already fixed in _check.py (Z406, Z503), "
        "rules.py (Z107, Z902), incremental.py (Z120, Z122, Z503), and "
        "scanner.py's own RuleFinding construction (Z106, Z902). Route "
        "through code_severity(issue) == 'warning' instead:\n"
        + "\n".join(violations)
    )
