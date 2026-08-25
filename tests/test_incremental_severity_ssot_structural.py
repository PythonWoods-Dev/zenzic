# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Structural guard for V031_INCREMENTAL_PY_SEVERITY_AUDIT.

Mirrors tests/test_finding_severity_ssot_structural.py's _check.py guard and
tests/test_rules_severity_ssot_structural.py's rules.py guard for
incremental.py's RuleFinding construction sites -- the third subsystem
found this session to construct finding objects. incremental.py imports and
constructs the exact same RuleFinding class rules.py does (not a distinct
type), so it is held to the identical rule: no bare string literal as the
severity= argument for a fixed code.

An exhaustive enumeration (not the prior session's bounded 6-site sample)
found three confirmed live violations here: Z120, Z122, and the
check_snippet_content() Z503 site (all hardcoded "error", codes.py says
"warning" for each) -- see test_incremental_severity_fix.py for the
behavioral reproduction.

This test parses incremental.py's AST directly and asserts that no
RuleFinding(...) call site passes a bare string literal as its severity=
keyword argument.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INCREMENTAL_PY_PATH = REPO_ROOT / "src" / "zenzic" / "core" / "incremental.py"


def _is_bare_string_literal(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _find_rule_finding_hardcodes() -> list[str]:
    """Return a list of "line N: severity='...'" violations, if any."""
    tree = ast.parse(
        INCREMENTAL_PY_PATH.read_text(encoding="utf-8"), filename=str(INCREMENTAL_PY_PATH)
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


def test_no_hardcoded_severity_literals_in_incremental_py() -> None:
    """No RuleFinding(...) call site in incremental.py may hardcode its
    severity= as a bare string literal for a fixed code -- it must be
    derived from codes.py's CODE_DEFINITIONS (the SSoT) via code_severity(),
    directly or indirectly.

    This test is proven to catch the bug class it guards against: run
    against the pre-fix committed state of this file, it fails with
    exactly the violations enumerated in V031_INCREMENTAL_PY_SEVERITY_AUDIT
    (Z201, Z503, Z410, Z411, Z124, Z121, Z122, Z120, Z123, Z203 x2, Z202,
    Z105, Z104, Z102 x2 -- 17 hardcoded-literal sites; three of them,
    Z120/Z122/Z503, were live severity mismatches, the rest were correct by
    coincidence).
    """
    violations = _find_rule_finding_hardcodes()
    assert not violations, (
        "Hardcoded severity literal(s) found in incremental.py's "
        "RuleFinding(...) construction -- this is the exact bug shape "
        "already found in _check.py (Z406, Z503) and rules.py (Z107, "
        "Z902). Route through code_severity(rule_id) instead:\n" + "\n".join(violations)
    )
