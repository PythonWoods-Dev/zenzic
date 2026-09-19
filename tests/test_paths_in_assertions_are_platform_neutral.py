# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A path compared as a string must be normalised, or it only passes on one platform.

Second instance this cycle. `test_the_unwired_indented_code_consumers_are_a_known_and_fixed_list`
compared `str(path)` against literals containing `/`: on Linux the prefix strip
matched and the assertion passed, on Windows the same path arrived as
`src\\zenzic\\core\\scanner.py` and it failed. **The set had not moved** — only the
spelling had. The verdict-cache counter broke the same way earlier.

The local gate runs on Linux and cannot see this, which is why it is a test
rather than a habit: the shape is mechanically findable, so it is found here
instead of on a Windows runner three pushes later.

**What it looks for**: a real filesystem path rendered into a string — `str(p)`
or an f-string interpolating one — compared against a literal containing `/`,
with no `as_posix()` anywhere in the comparison.

**What it deliberately does not flag**: `Path("a/b.md") == Path("a/b.md")`,
because `Path` normalises separators itself; URLs and route strings, which are
not filesystem paths; and a path stringified to be *passed* somewhere rather
than compared.

**A limit this cannot close, stated rather than left silent.** A *third*
instance of the platform-path class reached the Windows runner on 2026-09-19
and this file did not catch it:

    assert mounts == [(Path("/project/blog"), "blog")]
    # WindowsPath('D:/project/blog') != WindowsPath('/project/blog')

`Path` normalises separators. It does **not** supply a drive letter, and on
Windows an absolute path is drive *plus* root — so a rooted literal and a
resolved path are different paths, while on Linux they are the same one. The
exclusion above is right about separators and was silent about this.

It is stated here rather than implemented because the shape is not
distinguishable at the comparison. Nine other assertions in this suite compare a
computed value against a rooted `Path` literal — `result == Path("/docs/guide.md")`
— and every one is correct, because nothing resolved the other side. What made
the failing one wrong is what `build_content_mounts()` does *internally*, which
no rule reading the assertion can see. Flagging the syntax would report nine
false positives to catch one real defect, and a check with that ratio is
switched off within the month.

**What a reader must do instead**: when an assertion compares against a rooted
`Path` literal, ask whether the other side has been through `resolve()` or
`absolute()` anywhere in its history. If it has, compare against
`Path("/x").resolve()` rather than `Path("/x")`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


_TESTS = Path(__file__).resolve().parent
_SLASH_LITERAL = re.compile(r"""["'][^"']*/[^"']*["']""")
_PATH_NAME = re.compile(r"\b(path|file|p|src|root|dir)\b", re.IGNORECASE)


def _renders_a_path(node: ast.AST, source: str) -> bool:
    segment = ast.get_source_segment(source, node) or ""
    is_render = (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "str"
    ) or isinstance(node, ast.JoinedStr)
    return bool(is_render and _PATH_NAME.search(segment))


def _offenders() -> list[str]:
    """Flag a path normalised by **string surgery** instead of by `as_posix()`.

    This is the exact shape of the defect, and the check is deliberately narrow.
    A broader one was tried first — anything rendering a path inside a function
    that also compares against a slash literal — and it flagged assertion
    messages, subprocess arguments and already-normalised strings. A check that
    cries wolf is excluded, and an excluded check is not a check.

    So: `str(<something path-shaped>)` followed by `.replace(` whose argument is
    a literal containing `/`. That is someone trimming a prefix off a path by
    hand, which works on the platform they wrote it on and nowhere else.

    **What it does not cover**, stated rather than implied: a path rendered and
    compared across two statements with no string surgery between them. That
    form is dataflow, this check does not do dataflow, and the remedy for it is
    the one applied here — build paths with `relative_to(...).as_posix()` so the
    question never arises.
    """
    found: set[str] = set()
    for path in sorted(_TESTS.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "replace"):
                continue
            if not _renders_a_path(func.value, source):
                continue
            args = " ".join(ast.get_source_segment(source, a) or "" for a in node.args)
            if not _SLASH_LITERAL.search(args):
                continue
            segment = ast.get_source_segment(source, node) or ""
            found.add(f"{path.name}:{node.lineno}  {' '.join(segment.split())[:70]}")
    return sorted(found)


def test_the_instrument_finds_the_broken_shape() -> None:
    """A zero below is not evidence until this has found a known instance.

    The pair is the real defect and its real fix, so the check must tell them
    apart rather than flagging every line that mentions a path.
    """
    import tempfile

    broken = "x = [str(p).replace('src/zenzic/', '') for p in paths]"
    fixed = "x = [p.relative_to(root).as_posix() for p in paths]"
    with tempfile.TemporaryDirectory() as d:
        for name, snippet in (("b.py", broken), ("f.py", fixed)):
            (Path(d) / name).write_text(snippet, encoding="utf-8")
        global _TESTS
        real, _TESTS = _TESTS, Path(d)
        try:
            hits = _offenders()
        finally:
            _TESTS = real
    assert len(hits) == 1, hits
    assert hits[0].startswith("b.py:")


def test_no_assertion_compares_an_unnormalised_path() -> None:
    offenders = _offenders()
    assert not offenders, (
        "a path rendered with the platform's separator is compared to a literal "
        "containing '/'; this passes on Linux and fails on Windows:\n  " + "\n  ".join(offenders)
    )
