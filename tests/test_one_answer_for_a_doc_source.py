# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
""" "Is this file a documentation source?" must be answered in one place.

``core/discovery.py`` owns ``DOC_SUFFIXES``. Seven other sites answered the same
question with their own literal, and they agreed -- which is the whole hazard:
adding ``.markdown`` or ``.qmd`` to the authority would have left ``guard scan``'s
staged-file filter, the telemetry page count, the target resolver, the orphan-link
rule and three topology walks behind, and two of those are on the security-gate
path. Nothing anywhere said so.

This is the D4/D9 shape -- a frozen literal set duplicated beside a named constant
-- narrowed to the one set and made mechanical. A refactor closes the instances;
only a check keeps the class closed, because the next copy is written by someone
who has never read this file.

The rule: outside the authority, no collection literal in ``src/`` may contain
both ``.md`` and ``.mdx``, and no ``endswith``/``startswith`` call may test for
both. Import ``DOC_SUFFIXES`` instead -- and sort it where order is observable,
since a frozenset has none and determinism is Tier-0.
"""

from __future__ import annotations

import ast
from pathlib import Path


SRC = Path(__file__).resolve().parent.parent / "src" / "zenzic"

#: The file allowed to spell the set out: it is the definition.
AUTHORITY = SRC / "core" / "discovery.py"

_BOTH = {".md", ".mdx"}


def _literals(node: ast.AST) -> set[str]:
    """Every string constant directly inside a collection literal or call."""
    out: set[str] = set()
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            out.add(child.value.lower())
    return out


def _offenders() -> list[str]:
    found: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if path == AUTHORITY:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: set[str] = set()
            if isinstance(node, ast.Set | ast.Tuple | ast.List):
                names = {
                    e.value.lower()
                    for e in node.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)
                }
            elif isinstance(node, ast.BoolOp):
                # `x.endswith(".md") or x.endswith(".mdx")` -- same set, spelled
                # as control flow so a collection scan alone would miss it.
                for value in node.values:
                    if isinstance(value, ast.Call):
                        names |= _literals(value)
            if _BOTH <= names:
                rel = path.relative_to(SRC.parent.parent)
                found.append(f"{rel}:{getattr(node, 'lineno', '?')}")
    return found


def test_doc_suffixes_has_one_definition() -> None:
    offenders = _offenders()
    assert not offenders, (
        "these sites spell out the documentation suffixes instead of importing "
        "DOC_SUFFIXES from zenzic.core.discovery:\n  " + "\n  ".join(offenders)
    )


def test_the_detector_finds_a_planted_copy(tmp_path: Path) -> None:
    """A zero-result sweep is not evidence until the instrument has found something."""
    planted = tmp_path / "planted.py"
    planted.write_text('X = {".md", ".mdx"}\n', encoding="utf-8")
    tree = ast.parse(planted.read_text(encoding="utf-8"))
    hits = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Set | ast.Tuple | ast.List)
        and _BOTH
        <= {
            e.value.lower()
            for e in n.elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)
        }
    ]
    assert hits, "the detector cannot see a literal copy, so its silence means nothing"
