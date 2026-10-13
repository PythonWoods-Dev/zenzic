# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
""" "What does this run exclude?" must be built in one place.

``exclusion.build_exclusion_manager()`` is that place. It takes the adapter and
applies all three adapter-derived layers -- output directory, metadata files,
``exclude_docs``/``draft_docs`` -- so a caller cannot forget one by omission.

Seven sites constructed ``LayeredExclusionManager`` directly. Two were the CLI
bypasses the audit recorded as D3. The other four were not in that record and
were the ones that mattered, because they are the editor: ``lsp/server.py`` at
three sites and ``core/incremental.py`` at one, none of them passing any adapter
layer at all.

Measured on an MkDocs project with a built ``site/`` tree, scanning the
repository root:

    CLI              ['docs/index.md']
    LSP/incremental  ['docs/index.md', 'site/index.md']

So after a build, the editor analysed generated output that this same release
stopped analysing in the CLI -- the user got squiggles on a file CI says nothing
about. Two products for one condition.

This test is the control that keeps the answer in one place, and it carries a
positive control of its own: a planted direct construction it must find.
"""

from __future__ import annotations

import ast
from pathlib import Path


SRC = Path(__file__).resolve().parent.parent / "src" / "zenzic"

#: The module that defines the class and the builder: it constructs it by right.
AUTHORITY = SRC / "core" / "exclusion.py"

_CLASS = "LayeredExclusionManager"


def _constructions(tree: ast.AST) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == _CLASS
    ]


def test_the_exclusion_manager_is_constructed_in_one_place() -> None:
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if path == AUTHORITY:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for lineno in _constructions(tree):
            offenders.append(f"{path.relative_to(SRC.parent.parent)}:{lineno}")
    assert not offenders, (
        "these sites construct LayeredExclusionManager directly instead of calling "
        "build_exclusion_manager(), and so can omit an adapter layer by silence:\n  "
        + "\n  ".join(offenders)
    )


def test_the_detector_finds_a_planted_construction(tmp_path: Path) -> None:
    """A zero-result sweep is not evidence until the instrument has found something."""
    planted = tmp_path / "planted.py"
    planted.write_text("m = LayeredExclusionManager(config, repo_root=r)\n", encoding="utf-8")
    assert _constructions(ast.parse(planted.read_text(encoding="utf-8"))), (
        "the detector cannot see a direct construction, so its silence means nothing"
    )
