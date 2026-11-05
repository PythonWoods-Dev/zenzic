# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A finding's message must not restate the code the renderer already prints.

The reporter prefixes every finding with ``[Zxxx]``. Two construction sites
also put the code inside the message text, so the rendered line reads
``[Z601]  [Z601] Obsolete…`` and ``… in mkdocs.yml) [Z404]``. Cosmetic, and
still wrong: the duplicate is what a user pastes into an issue, and a message
carrying its own code invites a second copy to drift from ``codes.py``.

Structural rather than per-message: a new construction site added later is
covered without anyone remembering this file exists.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from zenzic.core import regex as re


SRC = Path(__file__).resolve().parents[1] / "src" / "zenzic"

#: ``[Z123]`` anywhere inside a string literal that becomes a finding message.
_CODE_TAG = re.compile(r"\[Z\d{3}\]")

#: Keyword arguments whose value is the human-readable message of a finding.
_MESSAGE_KWARGS = frozenset({"message"})

#: Classes whose construction produces a rendered finding line.
_FINDING_CLASSES = frozenset({"RuleFinding", "Finding"})


def _string_parts(node: ast.AST) -> list[str]:
    """Every literal string reachable inside *node*, including f-string text."""
    parts: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            parts.append(sub.value)
    return parts


def _offending_sites(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name not in _FINDING_CLASSES:
            continue
        for kw in node.keywords:
            if kw.arg not in _MESSAGE_KWARGS:
                continue
            for text in _string_parts(kw.value):
                if _CODE_TAG.search(text):
                    hits.append((node.lineno, text.strip()[:70]))
    # Adapter issue tuples: ``issues.append((path, "…message… [Zxxx]"))``. These
    # are not finding constructions -- they are collected and mapped to a code
    # later -- but the second element is rendered as the message, so the same
    # duplication reaches the same user. Without this branch the guard would
    # have protected one of the two sites this directive fixed.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "attr", "") != "append" or len(node.args) != 1:
            continue
        arg = node.args[0]
        if not isinstance(arg, ast.Tuple) or len(arg.elts) != 2:
            continue
        for text in _string_parts(arg.elts[1]):
            if _CODE_TAG.search(text):
                hits.append((node.lineno, text.strip()[:70]))

    # Positional-message call sites: RuleFinding(path, lineno, code, message, …)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name not in _FINDING_CLASSES or len(node.args) < 4:
            continue
        for text in _string_parts(node.args[3]):
            if _CODE_TAG.search(text):
                hits.append((node.lineno, text.strip()[:70]))
    return hits


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: p.name)
def test_no_finding_message_restates_its_own_code(path: Path) -> None:
    hits = _offending_sites(path)
    assert not hits, (
        f"{path.relative_to(SRC.parent.parent)} constructs a finding whose message "
        f"contains its own [Zxxx] tag, which the reporter prints again: {hits}"
    )


def test_the_detector_finds_a_planted_violation(tmp_path: Path) -> None:
    """A zero-result sweep proves nothing until the instrument has been shown to
    find something: a detector that silently stopped matching reports success in
    the same words as a clean tree."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "RuleFinding(path, 1, 'Z601', message='[Z601] something already prefixed')\n",
        encoding="utf-8",
    )
    assert _offending_sites(planted), "the detector missed a planted violation"
