# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Validation contracts for ``--format`` and ``--engine``.

``--only`` has always rejected an unknown finding code. ``--format`` accepted
anything and silently rendered text — including a value that is valid on a
*different* subcommand, so a CI step asking ``check assets`` for
``github-annotations`` received prose and no error. ``--engine`` had the
opposite failure: it rejected ``prebuilt``/``vsm``, which are real, fully
working engines, because its known-engine list came from entry points only
while adapter resolution also consults the built-in registry.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from zenzic.main import app


runner = CliRunner()


def _fixture(tmp_path: Path) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text(
        "# Home\n\nThis page carries ample prose so that the minimum word count "
        "check does not fire during flag-validation fixtures.\n",
        encoding="utf-8",
    )
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n', encoding="utf-8")
    return tmp_path


class TestFormatValidation:
    def test_unknown_format_is_rejected(self, tmp_path: Path) -> None:
        repo = _fixture(tmp_path)
        res = runner.invoke(app, ["check", "all", str(repo), "--format", "bogus"])
        assert res.exit_code != 0, "an unknown --format value was silently accepted"
        assert "bogus" in res.output
        assert "text" in res.output, "the error must name the valid options"

    def test_error_names_the_valid_options_for_that_command(self, tmp_path: Path) -> None:
        repo = _fixture(tmp_path)
        res = runner.invoke(app, ["check", "all", str(repo), "--format", "bogus"])
        for expected in ("text", "json", "sarif", "github-annotations"):
            assert expected in res.output, f"check all's error omits {expected!r}"

    def test_format_valid_elsewhere_is_rejected_where_unsupported(self, tmp_path: Path) -> None:
        """The failure that motivated this: ``github-annotations`` is valid on
        ``check all`` but unimplemented on ``check assets``, where it silently
        produced text despite a real finding.
        """
        repo = _fixture(tmp_path)
        res = runner.invoke(app, ["check", "assets", str(repo), "--format", "github-annotations"])
        assert res.exit_code != 0, (
            "check assets silently accepted a format it does not implement — "
            "a CI step consuming annotations would receive plain text instead"
        )
        assert "github-annotations" in res.output

    def test_supported_formats_still_work(self, tmp_path: Path) -> None:
        """Validation must not reject what the command genuinely supports."""
        repo = _fixture(tmp_path)
        for fmt in ("text", "json", "sarif", "github-annotations"):
            res = runner.invoke(app, ["check", "all", str(repo), "--format", fmt])
            assert res.exit_code in (0, 1), f"--format {fmt} was wrongly rejected: {res.output!r}"


class TestEngineValidation:
    def test_builtin_only_engines_are_accepted(self, tmp_path: Path) -> None:
        """``prebuilt`` and ``vsm`` resolve through the built-in registry and work
        end-to-end via config and auto-discovery; only the CLI gate rejected them.
        """
        repo = _fixture(tmp_path)
        (repo / ".zenzic-vsm.json").write_text(
            '{"routes": {"/": {"source": "index.md"}}}\n', encoding="utf-8"
        )
        for engine in ("prebuilt", "vsm"):
            res = runner.invoke(app, ["check", "all", str(repo), "--engine", engine, "--no-header"])
            assert "Unknown engine adapter" not in res.output, (
                f"--engine {engine} was rejected, but the same engine works via "
                f"[build_context] engine = {engine!r} and via auto-discovery"
            )

    def test_genuinely_unknown_engine_is_still_rejected(self, tmp_path: Path) -> None:
        repo = _fixture(tmp_path)
        res = runner.invoke(app, ["check", "all", str(repo), "--engine", "bogus"])
        assert res.exit_code != 0
        assert "Unknown engine adapter" in res.output

    def test_error_lists_every_selectable_engine(self, tmp_path: Path) -> None:
        repo = _fixture(tmp_path)
        res = runner.invoke(app, ["check", "all", str(repo), "--engine", "bogus"])
        for engine in ("mkdocs", "zensical", "standalone", "prebuilt", "vsm"):
            assert engine in res.output, f"the error omits the selectable engine {engine!r}"
