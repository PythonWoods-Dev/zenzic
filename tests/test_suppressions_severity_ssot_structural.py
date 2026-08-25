# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Structural guard for V031_FINAL_SEVERITY_SWEEP_AND_CONTENT_REMEDIATION.

Mirrors tests/test_rules_severity_ssot_structural.py's guard, applied to
suppressions.py, the seventh finding-construction subsystem found this
session to hardcode severity= as a bare string literal instead of deriving
it from codes.py via code_severity(). 4 sites confirmed (Z603 x1, Z620 x3)
-- all currently correct by coincidence, none yet a live bug, but
unguarded against the next codes.py edit.

This test parses suppressions.py's AST directly and asserts that no
RuleFinding(...) call site passes a bare string literal as its severity=
keyword argument.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SUPPRESSIONS_PY_PATH = REPO_ROOT / "src" / "zenzic" / "core" / "suppressions.py"


def _is_bare_string_literal(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _find_rule_finding_hardcodes() -> list[str]:
    """Return a list of "line N: severity='...'" violations, if any."""
    tree = ast.parse(
        SUPPRESSIONS_PY_PATH.read_text(encoding="utf-8"), filename=str(SUPPRESSIONS_PY_PATH)
    )
    violations: list[str] = []

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "RuleFinding":
            continue

        for kw in node.keywords:
            if kw.arg != "severity":
                continue
            value = kw.value
            if _is_bare_string_literal(value) and isinstance(value, ast.Constant):
                violations.append(
                    f"line {value.lineno}: RuleFinding(..., severity={value.value!r}) "
                    f"is a bare string literal -- must derive from codes.py via "
                    f"code_severity(rule_id) or an equivalent dynamic source."
                )

    return violations


def test_no_hardcoded_severity_literals_in_suppressions_py() -> None:
    """No RuleFinding(...) call site in suppressions.py may hardcode its
    severity= as a bare string literal for a fixed code -- it must be
    derived from codes.py's CODE_DEFINITIONS (the SSoT) via code_severity().

    Proven to catch the bug class it guards against: run against the
    pre-fix committed state of this file, it fails with exactly 4
    violations (Z603 x1, Z620 x3).
    """
    violations = _find_rule_finding_hardcodes()
    assert not violations, (
        "Hardcoded severity literal(s) found in suppressions.py's "
        "RuleFinding(...) construction -- this is the exact bug shape "
        "already found in _check.py, rules.py, incremental.py, scanner.py, "
        "and governance.py. Route through code_severity(rule_id) instead:\n"
        + "\n".join(violations)
    )
