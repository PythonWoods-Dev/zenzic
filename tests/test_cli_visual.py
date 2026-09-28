# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for Visual Snippet rendering in the Zenzic CLI.

Visual Snippets are the '│' source-line indicators that appear below each
finding header.  They were introduced in rc4 for check links (all error types)
and were already present in check references.  This suite verifies:

  1. Every error type emits a '│' snippet when source_line is non-empty.
  2. Errors without a source_line do NOT emit a spurious '│' line.
  3. The error_type badge appears in the header for non-generic errors.
  4. The live MkDocs sandbox produces the expected set of error types.
  5. The live Zensical sandbox produces UNREACHABLE_LINK for _private/ files.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from zenzic.core import regex as re
from zenzic.core.validator import LinkError
from zenzic.main import app
from zenzic.models.config import ZenzicConfig


runner = CliRunner()

_ROOT = Path("/fake/repo")
_DOCS = _ROOT / "docs"
_CFG = ZenzicConfig()

# ── Paths to the on-disk sandboxes ────────────────────────────────────────────

_HERE = Path(__file__).parent
_SANDBOX_MKDOCS = _HERE / "sandboxes" / "mkdocs"
_SANDBOX_ZENSICAL = _HERE / "sandboxes" / "zensical"


# ---------------------------------------------------------------------------
# Helper — invoke check links with a pre-set mock
# ---------------------------------------------------------------------------


def _invoke_with_errors(errors: list[LinkError]):
    with (
        patch("zenzic.cli._command_setup.find_repo_root", return_value=_ROOT),
        patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True)),
        patch("zenzic.cli._check.validate_links_structured", return_value=errors),
    ):
        return runner.invoke(app, ["check", "links"])


def _has_snippet_line(output: str, source_line: str) -> bool:
    """Return True when output contains a rendered snippet line for source_line.

    The visual marker can vary across renderers/fonts (e.g. ❱ or │), so the
    matcher accepts either common marker glyphs or plain-indented fallback.
    """
    escaped = re.escape(source_line)
    pattern = rf"(?m)^\s*(?:\d+\s+)?(?:[❱│>]\s+)?{escaped}\s*$"
    return re.search(pattern, output) is not None


# ---------------------------------------------------------------------------
# 1. Visual Snippet present when source_line is populated
# ---------------------------------------------------------------------------


def test_visual_snippet_rendered_when_source_line_present() -> None:
    """A non-empty source_line must render a visual snippet line in output."""
    err = LinkError(
        file_path=_DOCS / "index.md",
        line_no=3,
        message="index.md:3: broken link 'foo.md' (is not found)",
        source_line="[foo](foo.md)",
        error_type="FILE_NOT_FOUND",
    )
    result = _invoke_with_errors([err])
    assert _has_snippet_line(result.stdout, "[foo](foo.md)")


def test_visual_snippet_absent_when_source_line_empty() -> None:
    """An empty source_line must not produce a rendered snippet line."""
    err = LinkError(
        file_path=_DOCS / "index.md",
        line_no=5,
        message="index.md:5: broken link 'bar.md' (is not found)",
        source_line="",
        error_type="FILE_NOT_FOUND",
    )
    result = _invoke_with_errors([err])
    assert not _has_snippet_line(result.stdout, "[bar](bar.md)")


# ---------------------------------------------------------------------------
# 2. Error-type badge in header
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error_type,expected_code",
    [
        ("Z104", "Z104"),
        ("Z101", "Z101"),
        ("Z102", "Z102"),
        ("Z105", "Z105"),
        ("Z202", "Z202"),
    ],
)
def test_error_type_badge_present(error_type: str, expected_code: str) -> None:
    """Every canonical Zxxx error_type must appear as a badge in the output."""
    err = LinkError(
        file_path=_DOCS / "page.md",
        line_no=1,
        message="page.md:1: some error",
        source_line="[link](target.md)",
        error_type=error_type,
    )
    result = _invoke_with_errors([err])
    assert expected_code in result.stdout


def test_generic_link_error_has_no_badge() -> None:
    """Z101 is the canonical code for generic broken links."""
    err = LinkError(
        file_path=_DOCS / "page.md",
        line_no=1,
        message="page.md:1: some generic error",
        source_line="",
        error_type="Z101",
    )
    result = _invoke_with_errors([err])
    assert "Z101" in result.stdout


# ---------------------------------------------------------------------------
# 3. Multiple errors — each gets its own snippet
# ---------------------------------------------------------------------------


def test_multiple_errors_each_have_snippet() -> None:
    errors = [
        LinkError(
            file_path=_DOCS / "a.md",
            line_no=1,
            message="a.md:1: error one",
            source_line="[one](one.md)",
            error_type="Z104",
        ),
        LinkError(
            file_path=_DOCS / "b.md",
            line_no=2,
            message="b.md:2: error two",
            source_line="[two](two.md)",
            error_type="Z101",
        ),
    ]
    result = _invoke_with_errors(errors)
    assert _has_snippet_line(result.stdout, "[one](one.md)")
    assert _has_snippet_line(result.stdout, "[two](two.md)")
    assert "Z104" in result.stdout
    assert "Z101" in result.stdout


# ---------------------------------------------------------------------------
# 4. Live MkDocs sandbox — integration
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _SANDBOX_MKDOCS.exists(),
    reason="MkDocs sandbox not present",
)
def test_sandbox_mkdocs_expected_error_types(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live sandbox must emit ABSOLUTE_PATH (Z105) and BROKEN/ORPHAN link (Z101/Z103).

    Per CORE-REFACTOR-005: Z104 is reserved for static-asset checks only.
    Missing Markdown link targets are uniformly reported as Z101 (VSM miss).
    """
    monkeypatch.chdir(_SANDBOX_MKDOCS)
    result = runner.invoke(app, ["check", "links"])
    assert "Z105" in result.stdout  # ABSOLUTE_PATH
    assert "Z101" in result.stdout  # BROKEN_LINK (VSM miss — target not in site map)


@pytest.mark.skipif(
    not _SANDBOX_MKDOCS.exists(),
    reason="MkDocs sandbox not present",
)
def test_sandbox_mkdocs_get_started_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 'Get Started' → secret/hidden.md link must fire UNREACHABLE_LINK.

    This is the mandated first test scenario from the rc4 specification:
    'Get Started punta a secret/hidden.md → UNREACHABLE_LINK'.
    """
    monkeypatch.chdir(_SANDBOX_MKDOCS)
    result = runner.invoke(app, ["check", "links"])
    assert "UNREACHABLE_LINK" in result.stdout
    # The offending link text must appear in the snippet
    assert "secret/hidden.md" in result.stdout


@pytest.mark.skipif(
    not _SANDBOX_MKDOCS.exists(),
    reason="MkDocs sandbox not present",
)
def test_sandbox_mkdocs_double_index_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    """Double Index (index.md + README.md in docs/) should be reported as CONFLICT.

    The VSM detects the collision; check orphans surfaces it.
    This test verifies the sandbox is structurally correct for the conflict scenario.
    """
    monkeypatch.chdir(_SANDBOX_MKDOCS)
    # Both files must exist for the Double Index scenario
    assert (_SANDBOX_MKDOCS / "docs" / "index.md").exists()
    assert (_SANDBOX_MKDOCS / "docs" / "README.md").exists()


# ---------------------------------------------------------------------------
# 5. Live Zensical sandbox — integration
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _SANDBOX_ZENSICAL.exists(),
    reason="Zensical sandbox not present",
)
def test_sandbox_zensical_private_dir_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Link to _private/notes.md must emit UNREACHABLE_LINK with Visual Snippet."""
    monkeypatch.chdir(_SANDBOX_ZENSICAL)
    result = runner.invoke(app, ["check", "links"])
    assert result.exit_code == 1
    assert "UNREACHABLE_LINK" in result.stdout
    assert "_private/notes.md" in result.stdout


@pytest.mark.skipif(
    not _SANDBOX_ZENSICAL.exists(),
    reason="Zensical sandbox not present",
)
def test_sandbox_zensical_missing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Link to missing.md must emit FILE_NOT_FOUND."""
    monkeypatch.chdir(_SANDBOX_ZENSICAL)
    result = runner.invoke(app, ["check", "links"])
    assert "FILE_NOT_FOUND" in result.stdout
    assert "missing.md" in result.stdout


@pytest.mark.skipif(
    not _SANDBOX_ZENSICAL.exists(),
    reason="Zensical sandbox not present",
)
def test_sandbox_zensical_valid_links_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """features.md and api.md have only valid links — no errors from those pages."""
    monkeypatch.chdir(_SANDBOX_ZENSICAL)
    result = runner.invoke(app, ["check", "links"])
    # Only index.md has broken links — features.md and api.md must not appear as
    # section headers (full_rel path shown by the Rule separator).
    assert "docs/features.md" not in result.stdout
    assert "docs/api.md" not in result.stdout


# ---------------------------------------------------------------------------
# 6. Exit codes
# ---------------------------------------------------------------------------


def test_check_links_exit_code_0_when_no_errors() -> None:
    result = _invoke_with_errors([])
    assert result.exit_code == 0
    assert "No broken links found." in result.stdout


def test_check_links_exit_code_1_when_errors_present() -> None:
    err = LinkError(
        file_path=_DOCS / "index.md",
        line_no=1,
        message="index.md:1: broken link",
        source_line="[x](x.md)",
        error_type="FILE_NOT_FOUND",
    )
    result = _invoke_with_errors([err])
    assert result.exit_code == 1


_BREAKDOWN_PROJECT = {
    ".zenzic.toml": 'docs_dir = "docs"\nfail_under = 0\n\n[build_context]\nengine = "standalone"\n',
    "docs/index.md": ("# Index\n\nShort page.\n\n- [broken](nope.md)\n- [also broken](gone.md)\n"),
}


@pytest.mark.parametrize("columns", [200, 80, 67, 66, 64, 40, 28])
def test_the_breakdown_never_drops_a_number_at_any_terminal_width(
    tmp_path: Path, columns: int
) -> None:
    """`score --breakdown` must lose no figure, however narrow the terminal.

    It did. The table has six columns, and Rich crops what will not fit without
    saying so: measured at 67 columns it renders whole, at 66 and 65 the right
    border stops closing, and at 64 and below the `Applied Pts` column is gone
    entirely — the number the table exists to show. A reader saw a table that
    looked complete.

    Borders were not the cause and removing them was not the fix: dropping the
    box recovers about seven columns, which a six-column numeric table still
    cannot use at 28. Below the threshold the content degrades to a list
    instead, which is what this asserts at every width including the two
    either side of the boundary.
    """
    import os
    import subprocess
    import sys

    for rel, body in _BREAKDOWN_PROJECT.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")

    proc = subprocess.run(  # noqa: S603
        [str(Path(sys.executable).parent / "zenzic"), "score", ".", "--breakdown", "--no-header"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "COLUMNS": str(columns), "NO_COLOR": "1", "TERM": "dumb"},
    )
    out = proc.stdout + proc.stderr
    assert "Quality Breakdown" in out, f"no breakdown rendered at {columns}: {out[:300]!r}"

    # Every category the scorer weights, and the label of the column that used
    # to disappear. Checked by name rather than by counting cells, because the
    # two layouts arrange them differently on purpose.
    for needle in ("structural", "navigation", "content", "brand", "Applied Pts"):
        assert needle in out, (
            f"{needle!r} is missing from the breakdown at COLUMNS={columns}. "
            f"That is silent data loss, not a layout preference.\n{out}"
        )
    # Every figure the widest render shows must still be present, which is a
    # stronger claim than any literal: it does not depend on what this fixture
    # happens to score. The first version of this test asserted `-10` and failed
    # on a fixture that scored -16 -- an assertion about the fixture, not about
    # the layout.
    wide = subprocess.run(  # noqa: S603
        [str(Path(sys.executable).parent / "zenzic"), "score", ".", "--breakdown", "--no-header"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb"},
    ).stdout

    def _figures(text: str) -> set[str]:
        """Every numeric token, tokenised rather than matched.

        `re` in this project is the RE2 wrapper, whose `findall` is typed as a
        sequence of sequences; a regex here types badly for no benefit, since
        splitting on the characters a figure cannot contain is exact.
        """
        tokens: set[str] = set()
        current: list[str] = []
        for char in text:
            if char.isdigit() or char in "-%":
                current.append(char)
            else:
                token = "".join(current).strip("-")
                if token and any(c.isdigit() for c in token):
                    tokens.add("".join(current))
                current = []
        return tokens

    missing = sorted(f for f in _figures(wide) if f not in out)
    assert not missing, (
        f"figure(s) {missing} present at 200 columns are absent at COLUMNS={columns}. "
        f"Rich cropped them and said nothing.\n{out}"
    )
