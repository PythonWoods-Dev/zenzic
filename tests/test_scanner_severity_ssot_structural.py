# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Structural guard for V031_ADR093_ENFORCEMENT_FIX_AND_HYGIENE_CLOSEOUT Phase B.

Mirrors the three existing structural guards (_check.py, rules.py,
incremental.py) for scanner.py's RuleFinding construction sites -- the
fourth subsystem this session to construct finding objects with the same
"hardcoded severity literal bypasses codes.py" bug shape.

An exhaustive enumeration (not a sample) found two confirmed live
violations here: Z106 (CIRCULAR_LINK, hardcoded "error", codes.py says
"note"/info) and Z902 (RULE_TIMEOUT, hardcoded "error", codes.py says
"warning" -- a second, independent site for the exact bug already fixed
once this session in rules.py). See test_scanner_severity_fix.py for the
behavioral reproduction.

This test parses scanner.py's AST directly and asserts that no
RuleFinding(...) call site passes a bare string literal as its severity=
keyword argument. It does NOT scan Finding(...) call sites
(the CLI-layer reporter.py class) -- scanner.py's two Finding(...)
constructions (_map_credential_to_finding, Z201/Z204) use a bare
"security_breach" literal deliberately: this is the documented CLI-layer
security-severity bridge _check.py's own _finding_severity() docstring
already cross-references, not part of the RuleFinding SSoT concern this
test (and its three siblings) guards.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCANNER_PY_PATH = REPO_ROOT / "src" / "zenzic" / "core" / "scanner.py"


def _is_bare_string_literal(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _find_rule_finding_hardcodes() -> list[str]:
    """Return a list of "line N: severity='...'" violations, if any."""
    tree = ast.parse(SCANNER_PY_PATH.read_text(encoding="utf-8"), filename=str(SCANNER_PY_PATH))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id not in ("RuleFinding", "_RF"):  # _RF is scanner.py's local alias
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


def test_no_hardcoded_severity_literals_in_scanner_py() -> None:
    """No RuleFinding(...)/_RF(...) call site in scanner.py may hardcode its
    severity= as a bare string literal for a fixed code -- it must be
    derived from codes.py's CODE_DEFINITIONS (the SSoT) via code_severity(),
    directly or indirectly.

    This test is proven to catch the bug class it guards against: run
    against the pre-fix committed state of this file, it fails with
    exactly the two live violations found in
    V031_ADR093_ENFORCEMENT_FIX_AND_HYGIENE_CLOSEOUT (Z106, Z902), among
    six other hardcoded-but-coincidentally-correct sites (Z201, Z410,
    Z411, Z412, Z112, Z901).
    """
    violations = _find_rule_finding_hardcodes()
    assert not violations, (
        "Hardcoded severity literal(s) found in scanner.py's "
        "RuleFinding(...) construction -- this is the exact bug shape "
        "already found in _check.py (Z406, Z503), rules.py (Z107, Z902), "
        "and incremental.py (Z120, Z122, Z503). Route through "
        "code_severity(rule_id) instead:\n" + "\n".join(violations)
    )
