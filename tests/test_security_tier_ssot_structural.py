# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The Z2xx security tier has exactly one authority, and nothing restates it.

``_shared.py``'s SARIF emitter decided which findings make a run
``executionSuccessful: false`` with a hand-written ``{"Z201", ..., "Z205"}``
literal — a second copy of the security tier with nothing enforcing agreement.
It matched the real set, so nothing was wrong *today*; but a future ``Z206``
added to the tier would silently keep SARIF reporting the run as successful,
and SARIF is what CI dashboards and code-scanning integrations read.

Neither existing constant could serve as the alias: ``NON_SUPPRESSIBLE_CODES``
is broader (it carries the ``Z110``/``Z111`` config-abort codes, which are not
security findings) and ``SECURITY_FINDING_CODES`` is narrower (only the two
codes the credential scanner itself emits). So the tier gets its own SSoT,
``SECURITY_TIER_CODES``, and ``NON_SUPPRESSIBLE_CODES`` is composed from it —
one place to add a code, every consumer follows.
"""

from __future__ import annotations

import ast
from pathlib import Path

from zenzic.core.codes import NON_SUPPRESSIBLE_CODES, SECURITY_TIER_CODES


_SRC = Path(__file__).resolve().parent.parent / "src" / "zenzic"


def _string_sets(tree: ast.AST) -> list[tuple[int, frozenset[str]]]:
    """Every set/frozenset literal in a module, as (lineno, string members).

    Parsed rather than pattern-matched: the earlier regex scanned line by line,
    so it could only see a restatement written on a single physical line — and
    every multi-member frozenset in this codebase is formatted across several
    lines, because that is what ``ruff format`` produces. A copy written in the
    house style was therefore invisible to the guard protecting against copies.
    Verified: a multi-line restatement passed the regex version and fails this one.
    """
    found: list[tuple[int, frozenset[str]]] = []
    for node in ast.walk(tree):
        elts: list[ast.expr] | None = None
        if isinstance(node, ast.Set):
            elts = list(node.elts)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "frozenset"
            and node.args
            and isinstance(node.args[0], ast.Set)
        ):
            elts = list(node.args[0].elts)
        if elts is None:
            continue
        members = {
            e.value for e in elts if isinstance(e, ast.Constant) and isinstance(e.value, str)
        }
        if members:
            found.append((node.lineno, frozenset(members)))
    return found


def test_security_tier_is_the_full_z2xx_set() -> None:
    assert SECURITY_TIER_CODES == frozenset({"Z201", "Z202", "Z203", "Z204", "Z205"})


def test_non_suppressible_is_composed_from_the_tier_not_a_parallel_copy() -> None:
    """Composition, so a new tier code cannot be added to only one of them."""
    assert SECURITY_TIER_CODES < NON_SUPPRESSIBLE_CODES
    assert NON_SUPPRESSIBLE_CODES - SECURITY_TIER_CODES == frozenset({"Z110", "Z111"})


def test_no_module_restates_the_whole_security_tier_as_a_literal() -> None:
    """Fix the class, not the instance: catch a restatement anywhere in Core.

    Only a literal carrying the *entire* tier counts. A proper subset is a
    different concept, not a copy — ``codes.SECURITY_FINDING_CODES`` (moved
    here from ``scanner.py`` by ``V031_SECURITY_FIX_FULL_CLOSURE``) is
    ``{Z201, Z204}``, the codes the credential scanner itself emits, while
    ``Z202``/``Z203``/``Z205`` come from the traversal and scheme checks. Forcing
    that to alias the tier would couple two unrelated ideas and change behaviour;
    it is deliberately left alone.
    """
    offenders: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        if path.name == "codes.py":  # the SSoT itself is allowed to spell them out
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for lineno, members in _string_sets(tree):
            if members == SECURITY_TIER_CODES:
                rel = path.relative_to(_SRC.parent.parent)
                offenders.append(f"{rel}:{lineno}")
    assert not offenders, (
        "the Z2xx security tier is restated as a literal instead of imported from "
        "codes.SECURITY_TIER_CODES — a copy that agrees today drifts tomorrow:\n  "
        + "\n  ".join(offenders)
    )


def test_no_module_restates_the_security_severities_as_a_literal() -> None:
    """The severity pair has one authority too, and nothing may restate it.

    ``cli/_check.py`` introduced ``_SECURITY_SEVERITIES`` with a comment saying
    it is "named once so a presentation shortcut cannot return before the exit
    logic that consumes them" — and then restated the same two members as a bare
    literal about a thousand lines below it. Two matching literals governing
    whether a finding counts as a security finding, with nothing enforcing their
    agreement, is the same shape as the code-set duplication above.
    """
    from zenzic.cli._check import _SECURITY_SEVERITIES

    offenders: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for lineno, members in _string_sets(tree):
            if members == _SECURITY_SEVERITIES and path.name != "_check.py":
                offenders.append(f"{path.relative_to(_SRC.parent.parent)}:{lineno}")
            elif members == _SECURITY_SEVERITIES and path.name == "_check.py":
                # The definition itself is allowed exactly once.
                src_line = path.read_text(encoding="utf-8").splitlines()[lineno - 1]
                if "_SECURITY_SEVERITIES" not in src_line:
                    offenders.append(f"{path.relative_to(_SRC.parent.parent)}:{lineno}")
    assert not offenders, (
        "the security-severity pair is restated as a literal instead of imported "
        "from cli/_check.py's _SECURITY_SEVERITIES:\n  " + "\n  ".join(offenders)
    )
