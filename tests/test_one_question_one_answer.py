# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A path parameter that falls back to something different in each function is
one decision taken in several places.

Six duplication classes were found in this cycle and **every one was found by
accident**, while chasing an unrelated bug. What makes them invisible is that
the sites share no token: the answer is spelled as an inline expression at the
point of use, so it has no name to grep for, and what differs between sites is
the `else` branch rather than the condition a reader would compare. Worse, the
site that *was* fixed usually carries a comment explaining the rule — which
reads, at reviewing speed, as evidence the class was handled everywhere.

This is one mechanical form for that class. It walks `src/zenzic/`, collects
every `x: Path | None = None` parameter together with the expression its
function substitutes when it is `None`, and reports any parameter answered more
than one way across the package. It is purely syntactic and knows nothing about
this project.

On the day it was written it found `repo_root` answered five ways, one of them
`docs_root` — a line a comment ~500 lines above already argued against ("a docs
directory is not a repo root … harmless only because that path is rarely
reached"). It was reached: that fallback is why this repository printed, on
every run, a notice claiming its engine configuration was missing while
`mkdocs.yml` sat in the root. Naming a wrong line in a comment is not fixing it,
and a comment cannot fail a build.

`ACCEPTED_ANSWERS` is keyed on ``(parameter, expression)``, not on the parameter
alone, so accepting today's divergence does not accept tomorrow's: a *new* sixth
answer for `repo_root` still fails. Both directions are asserted, so an entry
that stops being true fails too.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

import pytest


SRC = Path(__file__).resolve().parent.parent / "src" / "zenzic"

#: ``(parameter, fallback expression)`` pairs that legitimately coexist, each
#: with the reason. A pair absent from here is a finding.
ACCEPTED_ANSWERS: dict[tuple[str, str], str] = {
    ("repo_root", "find_repo_root(fallback_to_cwd=True, search_from=docs_root)"): (
        "the correct answer, and the one the other sites were corrected towards: "
        "search upward from what is being scanned"
    ),
    ("repo_root", "docs_root.parent"): (
        "PrebuiltVSMAdapter's constructor, where it is dormant -- `from_repo()` "
        "always supplies a real root, and the adapter layer deliberately holds no "
        "import of `find_repo_root`. Wrong for a nested `docs_dir` such as "
        "'src/content/docs', which lands on 'src/content'; recorded rather than "
        "changed because closing it means giving an adapter a filesystem search"
    ),
    ("repo_root", "self._root_dir"): (
        "InMemoryPathResolver, which already holds its own root: for a resolver "
        "the instance's root *is* the repository root, not a guess at one"
    ),
    ("repo_root", "str(file_path.parent)"): (
        "governance policy context, which builds a string for pattern matching "
        "rather than a path to read from -- a different type answering a "
        "different question that happens to share the parameter name"
    ),
    ("docs_root", "str(file_path.parent)"): "same governance context, same reason",
    ("docs_root", "Path(route_source)"): (
        "governance again: a route's own source stands in for the docs root when "
        "evaluating a per-route policy, where no docs root is in scope"
    ),
}


def _optional_path_params(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Parameters annotated with a `Path` type and defaulting to `None`."""
    out: set[str] = set()
    a = fn.args
    positional = a.posonlyargs + a.args
    defaults = list(a.defaults or [])
    pairs = list(zip(positional[len(positional) - len(defaults) :], defaults, strict=False))
    pairs += [
        (arg, default)
        for arg, default in zip(a.kwonlyargs, a.kw_defaults or [], strict=False)
        if default is not None
    ]
    for arg, default in pairs:
        if not (isinstance(default, ast.Constant) and default.value is None):
            continue
        annotation = ast.unparse(arg.annotation) if arg.annotation else ""
        if "Path" in annotation:
            out.add(arg.arg)
    return out


def _fallbacks() -> dict[str, set[tuple[str, str]]]:
    """Map parameter name -> {(fallback expression, "path:line")}."""
    found: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for py in sorted(SRC.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        rel = py.relative_to(SRC.parent.parent).as_posix()
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            optional = _optional_path_params(fn)
            if not optional:
                continue
            for node in ast.walk(fn):
                # `if x is None: x = EXPR`
                if (
                    isinstance(node, ast.If)
                    and isinstance(node.test, ast.Compare)
                    and isinstance(node.test.left, ast.Name)
                    and node.test.left.id in optional
                    and len(node.test.ops) == 1
                    and isinstance(node.test.ops[0], ast.Is)
                    and isinstance(node.test.comparators[0], ast.Constant)
                    and node.test.comparators[0].value is None
                    and node.body
                    and isinstance(node.body[0], ast.Assign)
                ):
                    found[node.test.left.id].add(
                        (ast.unparse(node.body[0].value), f"{rel}:{node.lineno}")
                    )
                # `y = x if x is not None else EXPR`  /  `y = x if x else EXPR`
                if isinstance(node, ast.IfExp):
                    test = node.test
                    if (
                        isinstance(test, ast.Compare)
                        and isinstance(test.left, ast.Name)
                        and test.left.id in optional
                        and len(test.ops) == 1
                        and isinstance(test.ops[0], ast.IsNot)
                    ):
                        found[test.left.id].add((ast.unparse(node.orelse), f"{rel}:{node.lineno}"))
                    elif isinstance(test, ast.Name) and test.id in optional:
                        found[test.id].add((ast.unparse(node.orelse), f"{rel}:{node.lineno}"))
    return found


def test_the_instrument_finds_something() -> None:
    """A zero-result sweep is not evidence until the instrument has been shown
    to find something."""
    found = _fallbacks()
    assert "repo_root" in found, "the walker found no `repo_root` fallback at all"
    assert len(found) >= 8, f"only {len(found)} path parameters have a fallback: suspicious"


def test_no_path_parameter_answers_a_new_way() -> None:
    found = _fallbacks()
    unexplained: list[str] = []
    for name, answers in sorted(found.items()):
        if len({expr for expr, _ in answers}) < 2:
            continue  # one answer is the goal, not a finding
        for expr, where in sorted(answers):
            if (name, expr) not in ACCEPTED_ANSWERS:
                unexplained.append(f"  {name} falls back to `{expr}`  ({where})")
    assert not unexplained, (
        "a path parameter falls back to something no other site does, and nothing "
        "says why:\n" + "\n".join(unexplained)
    )


@pytest.mark.parametrize("pair", sorted(ACCEPTED_ANSWERS))
def test_each_accepted_answer_is_still_in_the_source(pair: tuple[str, str]) -> None:
    """An entry expires when the line it describes goes away."""
    name, expr = pair
    answers = _fallbacks().get(name, set())
    assert any(e == expr for e, _ in answers), (
        f"`{name}` no longer falls back to `{expr}` anywhere. Remove the entry: "
        f"{ACCEPTED_ANSWERS[pair][:70]}..."
    )
