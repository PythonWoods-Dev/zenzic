# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Structural guard for V031_RULES_PY_STRUCTURAL_FIX_AND_STRICT_FLAG_GAP.

Mirrors tests/test_finding_severity_ssot_structural.py's _check.py guard for
rules.py's RuleFinding construction sites. Two confirmed live violations were
found here (Z107, Z902) during the bounded rules.py sweep that followed the
_check.py fix -- the same architectural weakness in a second, independent
subsystem, not an isolated _check.py quirk.

This test parses rules.py's AST directly and asserts that no
RuleFinding(...) call site passes a bare string literal as its severity=
keyword argument. Accepted patterns are a call (code_severity(code)), or an
attribute access (self.severity / self.level -- CustomRule's and the base
Violation class's own dynamic, plugin-scoped fields, not tied to a fixed
codes.py entry). A bare ast.Constant string is the one pattern this test
forbids.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RULES_PY_PATH = REPO_ROOT / "src" / "zenzic" / "core" / "rules.py"


def _is_bare_string_literal(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _find_rule_finding_hardcodes() -> list[str]:
    """Return a list of "line N: severity='...'" violations, if any."""
    tree = ast.parse(RULES_PY_PATH.read_text(encoding="utf-8"), filename=str(RULES_PY_PATH))
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


def test_no_hardcoded_severity_literals_in_rules_py() -> None:
    """No RuleFinding(...) call site in rules.py may hardcode its severity=
    as a bare string literal for a fixed code -- it must be derived from
    codes.py's CODE_DEFINITIONS (the SSoT) via code_severity(), directly or
    indirectly.

    This test is proven to catch the bug class it guards against: run
    against the pre-fix committed state of this file (Z107 hardcoded
    "warning", Z902 hardcoded "error" at two sites), it fails with exactly
    those three violations. See
    V031_RULES_PY_STRUCTURAL_FIX_AND_STRICT_FLAG_GAP for the verification
    transcript.
    """
    violations = _find_rule_finding_hardcodes()
    assert not violations, (
        "Hardcoded severity literal(s) found in rules.py's RuleFinding(...) "
        "construction -- this is the exact bug shape already found in "
        "_check.py (Z406, Z503) and here (Z107, Z902). Route through "
        "code_severity(rule_id) instead:\n" + "\n".join(violations)
    )
