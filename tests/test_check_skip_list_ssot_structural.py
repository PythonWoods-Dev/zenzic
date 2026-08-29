# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Structural guard for V031_SKIPLIST_BUG_FAMILY_CLOSURE's Rule 21 recommendation.

``_check.py``'s rule-finding skip-list (codes already surfaced via a separate
path — ``link_codes`` for link-integrity findings, or the security-findings
bridge for credential findings — so they must not also surface a second time
via the generic rule-finding loop) was a manually-maintained tuple literal.
Four confirmed bugs this session (``Z202``/``Z203``/``Z108``/``Z201``/``Z204``
double-emissions) all had the same root cause: the literal drifted out of sync
with ``validator.py``'s ``link_codes`` set or ``scanner.py``'s security-findings
construction, one member at a time, across separate directives.

This test parses ``_check.py``'s AST directly and asserts that the skip-list
comparator is a derived expression (a ``Name``/``Attribute`` reference, or a
``BinOp``/set-operation built from one), never a hardcoded literal ``Tuple``
or ``Set`` containing 3 or more Z-code string constants. A literal of that
shape is exactly the pattern that caused all four prior bugs.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_PY_PATH = REPO_ROOT / "src" / "zenzic" / "cli" / "_check.py"


def _is_z_code_literal(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith("Z")
        and node.value[1:].isdigit()
    )


def _find_hardcoded_skip_list_literals() -> list[str]:
    """Return "line N: ..." violations for any hardcoded Z-code skip-list literal."""
    tree = ast.parse(CHECK_PY_PATH.read_text(encoding="utf-8"), filename=str(CHECK_PY_PATH))
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for op, comparator in zip(node.ops, node.comparators, strict=True):
            if not isinstance(op, ast.In):
                continue
            if not isinstance(comparator, (ast.Tuple, ast.Set, ast.List)):
                continue
            z_code_literals = [elt for elt in comparator.elts if _is_z_code_literal(elt)]
            if len(z_code_literals) >= 3:
                violations.append(
                    f"line {node.lineno}: hardcoded skip-list literal with "
                    f"{len(z_code_literals)} Z-code string constants -- must derive from "
                    f"validator.LINK_CODES / scanner.SECURITY_FINDING_CODES instead of "
                    f"a fresh literal that can silently drift out of sync."
                )

    return violations


def test_check_py_skip_list_is_not_a_hardcoded_literal() -> None:
    violations = _find_hardcoded_skip_list_literals()
    assert not violations, "\n".join(violations)


def test_check_py_skip_list_matches_the_real_ssot_derivation() -> None:
    """The actual skip-list _check.py uses must equal the SSoT-derived formula."""
    from zenzic.cli import _check
    from zenzic.core import scanner
    from zenzic.core.validator import LINK_CODES

    expected = (LINK_CODES - {"Z620"}) | scanner.SECURITY_FINDING_CODES
    assert _check._RULE_FINDING_SKIP_CODES == expected
