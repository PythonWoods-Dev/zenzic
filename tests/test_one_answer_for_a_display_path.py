# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
""" "What is this file's display path?" must be answered in one place.

``validator.repo_relative_label()`` is the authority and its docstring gives the
reason, which is not cosmetic: an absolute path leaks the checking machine's
directory layout into CI logs and SARIF, and it makes the same finding on the
same commit compare unequal between two machines, so no tool can diff two runs.

Nine sites answered it themselves -- seven byte-identical ``_rel()`` closures in
``cli/_check.py``, an inline copy in ``core/scanner.py``'s credential bridge, and
``core/reporter.py``'s ``_rel``, which was the one that actually differed: it
measured from ``docs_root`` rather than the repository root and returned ``str()``
rather than ``.as_posix()``, so it emitted native separators on Windows. That
last one turned out to have no callers at all, which is why nobody had seen it
produce a backslash.

The check is structural: a `try: X.relative_to(...)` / `except ValueError:`
fallback outside the authority is the shape being duplicated, whatever the
enclosing function is called.
"""

from __future__ import annotations

import ast
from pathlib import Path


SRC = Path(__file__).resolve().parent.parent / "src" / "zenzic"
AUTHORITY = SRC / "core" / "validator.py"


def _is_relative_to_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "relative_to"
    )


def _catches_value_error(handler: ast.ExceptHandler) -> bool:
    exc = handler.type
    if isinstance(exc, ast.Name):
        return exc.id == "ValueError"
    if isinstance(exc, ast.Tuple):
        return any(isinstance(e, ast.Name) and e.id == "ValueError" for e in exc.elts)
    return False


def _unwrap(value: ast.expr) -> ast.expr | None:
    """Strip the rendering and return what was rendered, or None if it was not.

    ``str(x)`` and ``x.as_posix()`` are the two spellings, and the difference
    between them is the Windows-separator bug this class already produced, not a
    difference in intent. A bare ``x.relative_to(y)`` is deliberately *not* a
    match: it yields a `Path` for further computation, which is a different
    question from "what do we print for this file".
    """
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "str":
        return value.args[0] if value.args else None
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute):
        if value.func.attr == "as_posix":
            return value.func.value
    return None


def _rendered_relative_to(value: ast.expr) -> str | None:
    unwrapped = _unwrap(value)
    if unwrapped is None:
        return None
    value = unwrapped
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute):
        if value.func.attr == "relative_to":
            return ast.unparse(value.func.value)
    return None


def _rendered_bare(value: ast.expr) -> str | None:
    unwrapped = _unwrap(value)
    return None if unwrapped is None else ast.unparse(unwrapped)


def _returns_label_of(node: ast.AST) -> str | None:
    """If *node* returns ``<name>.relative_to(...)`` rendered as a string, name it.

    ``p.relative_to(root).as_posix()`` and ``str(p.relative_to(root))`` both
    qualify: the difference between them is the Windows-separator bug this class
    already produced once, not a difference in intent.
    """
    if not isinstance(node, ast.Return) or node.value is None:
        return None
    return _rendered_relative_to(node.value)


def _assigns_label_of(node: ast.AST) -> str | None:
    """The same shape written as an assignment: ``rel = p.relative_to(root)...``."""
    if not isinstance(node, ast.Assign) or node.value is None:
        return None
    return _rendered_relative_to(node.value)


def _assigns_bare(node: ast.AST, name: str) -> bool:
    if not isinstance(node, ast.Assign) or node.value is None:
        return False
    return _rendered_bare(node.value) == name


def _returns_bare(node: ast.AST, name: str) -> bool:
    """Whether *node* returns *name* itself, rendered as a string."""
    if not isinstance(node, ast.Return) or node.value is None:
        return False
    return _rendered_bare(node.value) == name


def _offenders() -> list[str]:
    """The exact shape: relative-or-the-path-itself, as a display string.

    Deliberately not "any try/relative_to/except ValueError" -- that matches 55
    sites, most of them asking a different question ("is this inside that tree?")
    with a fallback that skips, returns None or raises. Those are not copies of
    the label; treating them as such would make the check noise, and a noisy
    check gets an exemption list, which is how a rule stops being one.
    """
    found: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        if path == AUTHORITY:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            if not any(_catches_value_error(h) for h in node.handlers):
                continue
            subject = next(
                (
                    n
                    for b in node.body
                    for x in ast.walk(b)
                    if (n := _returns_label_of(x) or _assigns_label_of(x))
                ),
                None,
            )
            if subject is None:
                continue
            for handler in node.handlers:
                if not _catches_value_error(handler):
                    continue
                if any(
                    _returns_bare(x, subject) or _assigns_bare(x, subject)
                    for b in handler.body
                    for x in ast.walk(b)
                ):
                    rel = path.relative_to(SRC.parent.parent)
                    found.append(f"{rel}:{node.lineno}")
    return found


def test_the_display_path_has_one_definition() -> None:
    offenders = _offenders()
    assert not offenders, (
        "these sites re-implement repo_relative_label() instead of calling it:\n  "
        + "\n  ".join(offenders)
    )


def test_the_detector_finds_a_planted_copy(tmp_path: Path) -> None:
    """A zero-result sweep is not evidence until the instrument has found something."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(p, root):\n"
        "    try:\n"
        "        return p.relative_to(root).as_posix()\n"
        "    except ValueError:\n"
        "        return p.as_posix()\n",
        encoding="utf-8",
    )
    tree = ast.parse(planted.read_text(encoding="utf-8"))
    hits = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Try)
        and any(_catches_value_error(h) for h in n.handlers)
        and any(_is_relative_to_call(x) for b in n.body for x in ast.walk(b))
    ]
    assert hits, "the detector cannot see a planted copy, so its silence means nothing"
