# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Code frames must resolve when ``docs_dir`` is a subdirectory.

``_render_snippet`` draws two context lines and a ``^^^^`` caret under the
offending token. It reads the file at ``self._docs_root / rel_path`` — but
``rel_path`` is project-relative and already carries the ``docs_dir`` prefix, so
for the ordinary ``docs_dir = "docs"`` layout the lookup asks for
``<repo>/docs/docs/index.md``. That path does not exist, ``_read_snippet``
returns ``None``, and the renderer falls through to its "file unreadable"
fallback: a single ``❱`` line, no context, no caret.

It regressed in ``a5d8157`` (2026-06-02), which moved the ``docs_dir`` prefix
into ``rel_path`` itself and reduced ``_full_rel`` to the identity. The rendered
*location* was byte-identical before and after, so nothing looked broken; only
the snippet lookup changed, and it fails silently into a plausible-looking line.

``docs_dir = "."`` was unaffected — the two paths coincide there — which is why
the repository's own tests never caught it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.main import app


_PAGE = (
    "# Welcome\n\n"
    "Line three here.\n\n"
    "This project was migrated from **OldPlatform** in Q1 2026.\n\n"
    "Line seven here.\n\n"
    "Line nine here.\n"
)
_CONFIG = '[governance]\nbrand_obsolescence = ["OldPlatform"]\n'


def _run(root: Path) -> str:
    result = CliRunner().invoke(
        app, ["check", "all", str(root / "docs"), "--no-header"], catch_exceptions=False
    )
    return result.output


def _build(tmp_path: Path, docs_dir: str, page_at: str) -> Path:
    (tmp_path / "mkdocs.yml").write_text("site_name: T\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text(
        f'docs_dir = "{docs_dir}"\n\n{_CONFIG}', encoding="utf-8"
    )
    page = tmp_path / page_at
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(_PAGE, encoding="utf-8")
    return tmp_path


class TestSubdirectoryDocsRoot:
    """The ordinary MkDocs layout — the one that regressed."""

    def test_the_caret_row_is_rendered(self, tmp_path: Path) -> None:
        _build(tmp_path, "docs", "docs/index.md")
        output = _run(tmp_path)
        assert "^^^^^^^^^^^" in output, (
            "no caret row under the offending token — the snippet path did not "
            f"resolve and the renderer fell back to a bare line:\n{output}"
        )

    def test_the_surrounding_context_lines_are_rendered(self, tmp_path: Path) -> None:
        """``_CONTEXT_LINES = 2``: the frame is five rows, not one."""
        _build(tmp_path, "docs", "docs/index.md")
        output = _run(tmp_path)
        assert "Line three here." in output, f"no leading context row:\n{output}"
        assert "Line seven here." in output, f"no trailing context row:\n{output}"


class TestCaretNeverOverrunsItsLine:
    """A caret marks a span *of the rendered line*; it cannot be longer than it.

    ``caret_len`` was ``len(match_text)``, and for HTML findings *match_text* is
    the whole raw tag — which may span several source lines. The caret is drawn
    under the error line alone, so a multi-line tag produced a caret far wider
    than the text beneath it: in the shipped ``z120`` gallery example, a 103
    character caret under a two character line (``<a``).
    """

    def test_a_multiline_tag_does_not_produce_a_caret_wider_than_its_line(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "mkdocs.yml").write_text("site_name: T\n", encoding="utf-8")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs/index.md").write_text(
            "# Title\n\nSome introductory prose to carry the page.\n\n"
            "<a\n"
            '  href="./target.md"\n'
            '  hreflang="en"\n'
            "  >Link text here</a>\n\n"
            "More prose so the page is not otherwise empty at all.\n",
            encoding="utf-8",
        )
        (tmp_path / "docs/target.md").write_text("# Target\n\nSome words here.\n", encoding="utf-8")

        output = (
            CliRunner()
            .invoke(
                app,
                ["check", "all", str(tmp_path / "docs"), "--no-header"],
                catch_exceptions=False,
            )
            .output
        )

        for line in output.split("\n"):
            stripped = line.strip()
            if set(stripped.replace("│", "").strip()) == {"^"}:
                caret_len = stripped.count("^")
                assert caret_len <= len("<a"), (
                    f"caret is {caret_len} characters wide but the line it marks "
                    f"(`<a`) is {len('<a')} — it overruns its own source line:\n{output}"
                )


class TestLayoutsThatMustNotChange:
    """The fix strips a prefix; where there is none to strip it is a no-op."""

    def test_a_repo_root_docs_dir_still_renders_its_caret(self, tmp_path: Path) -> None:
        # The page sits at the repository root: with docs_dir = "." there is no
        # prefix on rel_path, so this is precisely the no-op the fix must preserve.
        (tmp_path / ".zenzic.toml").write_text(f'docs_dir = "."\n\n{_CONFIG}', encoding="utf-8")
        (tmp_path / "index.md").write_text(_PAGE, encoding="utf-8")
        result = CliRunner().invoke(
            app, ["check", "all", str(tmp_path), "--no-header"], catch_exceptions=False
        )
        assert "^^^^^^^^^^^" in result.output, result.output

    @pytest.mark.parametrize("docs_dir", ["src/docs", "content/pages"])
    def test_a_multi_segment_docs_dir_resolves_too(self, tmp_path: Path, docs_dir: str) -> None:
        """Stripping must handle a nested root, not just a single segment."""
        _build(tmp_path, docs_dir, f"{docs_dir}/index.md")
        result = CliRunner().invoke(
            app,
            ["check", "all", str(tmp_path / docs_dir), "--no-header"],
            catch_exceptions=False,
        )
        assert "^^^^^^^^^^^" in result.output, result.output
