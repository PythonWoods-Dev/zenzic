# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Structural guard: no hardcoded "security_breach"/"security_incident" string
literal may exist as a Finding/RuleFinding severity= argument anywhere in the
credential/finding-construction path.

An SDK v3 rule declaring code="Z201" exposed a real, live defect: two
independent authorities for "what severity does Z201/Z204 carry" — codes.py's
exit_contract_severity() (which only special-cased Z203/Z205) and
core/scanner.py's _map_credential_to_finding (which hardcoded
severity="security_breach" for Z201/Z204 directly). They silently drifted
apart. The fix eliminated the hardcoded literal entirely in favour of direct
derivation from exit_contract_severity() — a structural drift-guard on a
literal that no longer exists would be a weaker substitute for the same
guarantee, not a stronger one. This test asserts the literal itself is gone.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCANNER_PY_PATH = REPO_ROOT / "src" / "zenzic" / "core" / "scanner.py"

_FORBIDDEN_SEVERITY_LITERALS = {"security_breach", "security_incident"}


def _find_hardcoded_severity_literals(source_path: Path) -> list[str]:
    """Return "line N: ..." violations for any severity=<string literal>
    keyword argument whose value is one of the forbidden literals."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg != "severity":
                continue
            if (
                isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
                and kw.value.value in _FORBIDDEN_SEVERITY_LITERALS
            ):
                violations.append(
                    f"{source_path.name}:{node.lineno}: severity={kw.value.value!r} is a "
                    "hardcoded literal — derive it from codes.exit_contract_severity(code) "
                    "instead, the single authority for the Z2xx exit-contract tier."
                )

    return violations


def test_scanner_py_has_no_hardcoded_security_severity_literal() -> None:
    violations = _find_hardcoded_severity_literals(SCANNER_PY_PATH)
    assert not violations, "\n".join(violations)


def test_check_py_has_no_hardcoded_security_severity_literal() -> None:
    check_py_path = REPO_ROOT / "src" / "zenzic" / "cli" / "_check.py"
    violations = _find_hardcoded_severity_literals(check_py_path)
    assert not violations, "\n".join(violations)


def test_map_credential_to_finding_derives_severity_from_the_choke_point() -> None:
    """Positive assertion: the real call site uses exit_contract_severity(code),
    not any other expression — confirms the derivation is genuinely wired,
    not merely absent-by-coincidence (e.g. a refactor that deleted the keyword
    argument entirely would also pass the two tests above without fixing
    anything)."""
    tree = ast.parse(SCANNER_PY_PATH.read_text(encoding="utf-8"), filename=str(SCANNER_PY_PATH))

    func_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_map_credential_to_finding":
            func_node = node
            break
    assert func_node is not None, "_map_credential_to_finding not found in scanner.py"

    severity_call_exprs: list[str] = []
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg == "severity":
                severity_call_exprs.append(ast.dump(kw.value))

    assert len(severity_call_exprs) == 2, (
        f"expected exactly 2 severity= keyword arguments (Z204 and Z201 branches), "
        f"found {len(severity_call_exprs)}"
    )
    for expr in severity_call_exprs:
        assert "exit_contract_severity" in expr, (
            f"severity= argument does not call exit_contract_severity(): {expr}"
        )
