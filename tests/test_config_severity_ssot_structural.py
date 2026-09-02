# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Structural guard for V031_Z110_Z111_SEVERITY_SSOT_FIX.

Mirrors tests/test_suppressions_severity_ssot_structural.py's guard, applied
to models/config.py -- the eighth finding-construction subsystem found to
hardcode severity= as a bare string literal instead of deriving it from
codes.py via code_severity(). 3 sites confirmed (Z110 x1, Z111 x2), all
correct by coincidence today, none yet a live bug, but unguarded against the
next codes.py edit to either code.

Found only on the second sweep: the first pass had no execution capability
and dismissed config.py as an unrelated subsystem without opening it. See
Rule 32.

This test parses config.py's AST directly and asserts that no Finding(...)
call site passes a bare string literal as its severity= keyword argument.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PY_PATH = REPO_ROOT / "src" / "zenzic" / "models" / "config.py"


def _is_bare_string_literal(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _find_finding_hardcodes() -> list[str]:
    """Return a list of "line N: severity='...'" violations, if any."""
    tree = ast.parse(CONFIG_PY_PATH.read_text(encoding="utf-8"), filename=str(CONFIG_PY_PATH))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "Finding":
            continue

        for kw in node.keywords:
            if kw.arg != "severity":
                continue
            value = kw.value
            if _is_bare_string_literal(value) and isinstance(value, ast.Constant):
                violations.append(
                    f"line {value.lineno}: Finding(..., severity={value.value!r}) "
                    f"is a bare string literal -- must derive from codes.py via "
                    f"code_severity(code)."
                )

    return violations


def test_no_hardcoded_severity_literals_in_config_py() -> None:
    """No Finding(...) call site in config.py may hardcode its severity= as a
    bare string literal for a fixed code -- it must be derived from codes.py's
    CODE_DEFINITIONS (the SSoT) via code_severity().

    Proven to catch the bug class it guards against: run against the pre-fix
    state of this file, it fails with exactly 3 violations (Z110 x1, Z111 x2).
    """
    violations = _find_finding_hardcodes()
    assert not violations, (
        "Hardcoded severity literal(s) found in config.py's Finding(...) "
        "construction -- this is the exact bug shape already found in "
        "_check.py, rules.py, incremental.py, scanner.py, governance.py, and "
        "suppressions.py. Route through code_severity(code) instead:\n"
        + "\n".join(violations)
    )
