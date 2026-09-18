# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The container vocabulary reaches every consumer, and cannot be forgotten.

Three separate guarantees, because they fail in three different ways:

1. **Structural** -- a content function that builds a ``BlockTracker`` declares
   ``containers`` keyword-only with no default. This is the one that catches a
   *fourteenth function* added later with a convenient default.
2. **Mechanical** -- a caller that omits it fails loudly. ``mypy --strict``
   catches this statically (``Missing named argument "containers"``); the test
   below pins the runtime half, so the guarantee survives a suite run with no
   type-checker.
3. **Behavioural** -- the vocabulary actually changes what is read. A project
   enabling only ``admonition`` must stop recognising ``???``. Without this,
   the two guarantees above would protect a value nobody uses.

Why this file exists at all: thirteen call sites across four files is exactly
the surface where the fourteenth gets forgotten, and this cycle measured that
class repeatedly -- four copies of href resolution, thirty-one fence
implementations, four instances of ``[^>]*``.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from zenzic.core import content
from zenzic.core.ast import BlockTracker
from zenzic.core.extensions import EnabledExtensions, container_pattern
from zenzic.core.rules import AdaptiveRuleEngine


_CONTENT_SRC = Path(inspect.getfile(content))

#: The installed package's own directory, so that paths in assertions are
#: independent of the working directory and of the platform's separator.
_PACKAGE_ROOT = _CONTENT_SRC.resolve().parent.parent


def _functions_building_a_tracker() -> list[ast.FunctionDef]:
    """Every module-level function in ``content`` that constructs a BlockTracker."""
    tree = ast.parse(_CONTENT_SRC.read_text(encoding="utf-8"))
    found = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Name)
                and sub.func.id == "BlockTracker"
            ):
                found.append(node)
                break
    return found


# ── 1. Structural ─────────────────────────────────────────────────────────────


def test_the_instrument_finds_something() -> None:
    """The sweep below is not evidence until the instrument has found something."""
    names = [f.name for f in _functions_building_a_tracker()]
    assert len(names) == 13, f"expected 13 tracker-building functions, found {names}"


def test_every_tracker_building_function_requires_its_vocabulary() -> None:
    """A default here would be reachable by omitting one keyword at one call site.

    This is the check that catches a *fourteenth function*, not a fourteenth
    caller: someone adding ``check_something(path, text, containers=None)``
    restores the silent default for that rule alone, and no caller is wrong.
    """
    offenders = []
    for fn in _functions_building_a_tracker():
        kwonly = {a.arg for a in fn.args.kwonlyargs}
        positional = {a.arg for a in fn.args.args}
        if "containers" not in kwonly:
            offenders.append(
                f"{fn.name}: 'containers' is "
                + ("positional" if "containers" in positional else "absent")
            )
            continue
        index = [a.arg for a in fn.args.kwonlyargs].index("containers")
        if fn.args.kw_defaults[index] is not None:
            offenders.append(f"{fn.name}: 'containers' has a default")
    assert not offenders, "container vocabulary is omissible in:\n  " + "\n  ".join(offenders)


# ── 2. Mechanical ─────────────────────────────────────────────────────────────


def test_a_forgotten_caller_fails_at_runtime() -> None:
    """The fourteenth call site, written without the vocabulary."""
    with pytest.raises(TypeError, match="containers"):
        content.check_bare_urls(Path("doc.md"), "text")  # type: ignore[call-arg]


def test_the_engine_requires_its_vocabulary() -> None:
    """The run-scoped carrier refuses to be built without the run's answer."""
    with pytest.raises(TypeError, match="containers"):
        AdaptiveRuleEngine([])  # type: ignore[call-arg]


# ── 3. Behavioural ────────────────────────────────────────────────────────────

_DOC = """!!! note "Note"

    admonition body

??? details "Details"

    details body
"""


def _read_as_code(text: str, enabled: EnabledExtensions | None) -> list[str]:
    tracker = BlockTracker(container_pattern(enabled))
    out = []
    for line in text.splitlines():
        tracker.feed(line)
        if line.strip() and tracker.in_indented_code:
            out.append(line.strip())
    return out


def test_a_project_enabling_only_admonition_stops_recognising_details() -> None:
    """The assertion the extension contract exists for.

    ``???`` comes from `pymdownx.details`. A project that does not enable it
    never writes a details block, so four spaces after ``??? details`` is an
    indented code block -- and its content must not be scanned as prose.
    """
    only_admonition = EnabledExtensions(names=frozenset({"admonition"}))
    read_as_code = _read_as_code(_DOC, only_admonition)
    assert "details body" in read_as_code
    assert "admonition body" not in read_as_code


def test_the_default_vocabulary_would_not_have_caught_it() -> None:
    """Proof that the assertion above would have failed before the wiring.

    ``None`` is what every consumer received while the vocabulary was declared
    on the context and never assigned: the full four-marker default, regardless
    of what the project enables.
    """
    assert _read_as_code(_DOC, None) == []


def test_both_corpora_keep_the_full_vocabulary() -> None:
    """The measured corpora enable all four markers, so the wiring must not move them."""
    every_marker = EnabledExtensions(
        names=frozenset({"admonition", "pymdownx.details", "pymdownx.tabbed", "def_list"})
    )
    assert _read_as_code(_DOC, every_marker) == _read_as_code(_DOC, None) == []


# ── 4. The eager-resolution reach ─────────────────────────────────────────────


def test_a_broken_engine_config_still_reports_rather_than_aborting_here() -> None:
    """The eager resolution adds no new failure mode for a broken engine config.

    Measured: a repository declaring `engine = "zensical"` with no
    `zensical.toml` already raised `ZenzicConfigError` from the pre-existing
    `get_adapter` call in `_run_vsm_and_urp_pass`, and every CLI entry point
    builds its own adapter first and reports it there (exit 1, no traceback).

    So `resolve_container_vocabulary` carries **no guard**: a `try/except` there
    would be a branch no measured path can reach. This test pins the reason, so
    that a future reader does not re-add one as an obvious precaution.
    """
    import inspect

    from zenzic.core import scanner

    source = inspect.getsource(scanner.resolve_container_vocabulary)
    assert "try:" not in source, (
        "a guard here would be unreachable -- see the measurement in the docstring"
    )
    assert "No guard around this call" in source, "the reason must stay written down"


def test_the_repo_root_fallback_is_not_the_docs_root(tmp_path: Path) -> None:
    """A docs directory is not a repo root, and the adapter reads config from the root it is given.

    The pre-existing fallback at the security-URP call site passes `docs_root`
    when `repo_root` is None. That was harmless only because that path is rarely
    reached; resolving the vocabulary eagerly would have made it reachable on
    every scan, and it is what made the adapter look for `zensical.toml` inside
    `docs/`.
    """
    from zenzic.core.scanner import resolve_container_vocabulary
    from zenzic.models.config import ZenzicConfig

    (tmp_path / "docs").mkdir()
    (tmp_path / "mkdocs.yml").write_text(
        "site_name: T\nmarkdown_extensions:\n  - admonition\n", encoding="utf-8"
    )
    config, _ = ZenzicConfig.load(tmp_path)

    # repo_root omitted: the resolver must still find the root that holds mkdocs.yml.
    pattern = resolve_container_vocabulary(config, tmp_path / "docs")
    assert pattern.match("!!! note"), "admonition is enabled and must be recognised"
    assert not pattern.match("??? details"), "pymdownx.details is not enabled here"


# ── 5. The gallery exercises the contract ─────────────────────────────────────


def test_the_declaring_gallery_fixture_behaves_differently_from_the_default() -> None:
    """`examples/z406-nav-contract` is the one fixture that declares its extensions.

    The other 139 declare none, so they all receive the default vocabulary and
    the gallery never exercised the path this contract serves.

    This one enables `admonition` and not `pymdownx.details`, so `!!!` opens a
    container in it and `???` does not. Its `???` block holds a heading ending
    in a period -- `Z517 HEADING_PUNCTUATION` -- which is never read as a
    heading there, because four spaces under a non-container is a CommonMark
    §4.4 code block.

    The assertion is the difference, not the absence: the same file under the
    default vocabulary reports the finding.
    """
    from zenzic.core import content

    fixture = Path("examples/z406-nav-contract/docs/index.md")
    text = fixture.read_text(encoding="utf-8")

    declared = container_pattern(EnabledExtensions(names=frozenset({"admonition"})))
    default = container_pattern(None)

    as_declared = content.check_heading_punctuation(fixture, text, containers=declared)
    as_default = content.check_heading_punctuation(fixture, text, containers=default)

    assert len(as_declared) == 0, "the project does not enable pymdownx.details"
    assert len(as_default) == 1, "under the default vocabulary the heading is read"


# ── 6. The consumers outside content.py ───────────────────────────────────────


def _indent_consumers() -> list[tuple[str, str, bool]]:
    """Every function in `src/` that reads `in_indented_code`, and whether it was handed a vocabulary."""
    import ast

    rows = []
    for path in sorted(_PACKAGE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            builds = [
                n
                for n in ast.walk(node)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == "BlockTracker"
            ]
            if not builds:
                continue
            reads = any(
                isinstance(n, ast.Attribute) and n.attr == "in_indented_code"
                for n in ast.walk(node)
            )
            if reads:
                rows.append(
                    (
                        # `as_posix()` and relative to the package root, not
                        # `str(path)` against the working directory. On Windows
                        # the first gives `src\\zenzic\\core\\scanner.py` and the
                        # prefix strip below never matched, so this assertion
                        # failed there and only there -- the set had not moved.
                        path.relative_to(_PACKAGE_ROOT).as_posix(),
                        node.name,
                        bool(builds[0].args or builds[0].keywords),
                    )
                )
    return rows


def test_the_unwired_indented_code_consumers_are_a_known_and_fixed_list() -> None:
    """Twenty functions read `in_indented_code`; six still take the default.

    The thirteen in `content.py` are wired, and so are three in `governance.py`
    and three in `rules.py`. The five below extract anchors, reference
    definitions and links rather than running content rules, and reaching them
    means threading the vocabulary through 49 call sites plus `ReferenceScanner`
    — measured 2026-09-18, larger than the thirteen.

    `tab_anchors_in` joined the list when `Z102` was closed: it is the single
    implementation of the content-tab anchor rule, shared by `anchors_in_file`
    and the scanner's preloaded-cache branch. It takes the project's tab style
    but not yet its container vocabulary, so it is counted here rather than
    quietly excluded.

    The residual error has a direction and it is the forgiving one: these five
    receive the **full** four-marker vocabulary, so they read container bodies
    as content. On a project that writes `???` without enabling
    `pymdownx.details` they collect anchors and links from what is really a code
    block, which can produce a false `Z101` and can only make `Z102` *less*
    likely to fire, never more.

    This test exists so the list cannot grow in silence. A new unwired consumer
    fails it; wiring one of these fails it too, and the fix is to delete the
    name.
    """
    unwired = sorted(f"{p}::{n}" for p, n, w in _indent_consumers() if not w)
    assert unwired == [
        "core/scanner.py::harvest",
        "core/validator.py::_build_ref_map",
        "core/validator.py::_extract_empty_link_texts",
        "core/validator.py::anchors_in_file",
        "core/validator.py::extract_ref_links",
        "core/validator.py::tab_anchors_in",
    ], f"the unwired set moved: {unwired}"


def test_the_credential_scanner_does_not_skip_indented_blocks() -> None:
    """`harvest` is on the list above, and this is why that is safe.

    Its `in_indented_code` guard gates *content* events — reference definitions
    — and the credential findings are collected before that loop runs. A secret
    indented four spaces is still reported. If that ever changes, a secret
    inside an indented block becomes invisible, which is the one direction this
    whole mechanism must never take.
    """
    import inspect

    from zenzic.core.scanner import ReferenceScanner

    source = inspect.getsource(ReferenceScanner.harvest)
    credentials_at = source.index("credential_events.append")
    guard_at = source.index("in_indented_code")
    assert credentials_at < guard_at, (
        "credential collection must stay above the indented-code guard"
    )
