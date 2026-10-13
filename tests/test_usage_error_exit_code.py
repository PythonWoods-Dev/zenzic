# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A CLI usage error must not be indistinguishable from a credential breach.

The Exit Code Contract reserves exit 2 for a Credential Scanner Breach, "never
suppressible". Click's default for a usage error — an unknown option, an
unknown command, a missing subcommand — is also 2, so a typo'd flag and a live
AWS key produced the same exit code and no CI gate could tell them apart.

The collision is not theoretical: it misled an adversarial audit of this very
contract three separate times, because this shell (zsh) does not word-split
unquoted expansions, so ``zenzic $cmd`` with a two-word value became a usage
error whose exit 2 read as a security gate firing.

Usage errors are remapped to exit 1 — the quality/error tier — leaving exit 2
exclusive to the security tier it is documented to mean.

**The remap is scoped to Zenzic's own entry point.** ``exit_code`` is a class
attribute on a class Zenzic does not own, and the first fix set it at import
time: importing ``zenzic.main`` silently changed the exit code of every other
Click application in the same interpreter. These tests therefore drive
``cli_main`` — the real console-script boundary, where the contract applies —
and pin that an unrelated Click app is unaffected.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
import pytest
from typer.testing import CliRunner

from zenzic.main import _usage_errors_exit_1, app, cli_main


_SECRET = "AKIA" + "IOSFODNN7EXAMPLE"
_PROSE = "Prose long enough to clear the minimum word-count check comfortably here."


def _run_entry_point(argv: list[str], monkeypatch: pytest.MonkeyPatch) -> int | str | None:
    """Invoke the real console-script entry point and return its exit code."""
    monkeypatch.setattr(sys, "argv", ["zenzic", *argv])
    with pytest.raises(SystemExit) as excinfo:
        cli_main()
    return excinfo.value.code


@pytest.mark.parametrize(
    ("label", "argv"),
    [
        ("unknown option", ["check", "all", "--definitely-not-a-flag"]),
        ("unknown command", ["definitely-not-a-command"]),
        ("unknown subcommand", ["check", "definitely-not-a-subcommand"]),
    ],
)
def test_usage_errors_exit_1_not_2(
    label: str, argv: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    code = _run_entry_point(argv, monkeypatch)
    assert code == 1, (
        f"{label} exited {code}; exit 2 is reserved for the security "
        f"tier and a usage error must not be mistakable for a credential breach"
    )


def test_a_real_credential_still_exits_2(tmp_path: Path) -> None:
    """The other half: remapping usage errors must not touch the security tier."""
    (tmp_path / "mkdocs.yml").write_text("site_name: Demo\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n', encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text(f'# P\n\n{_PROSE}\n\naws_key = "{_SECRET}"\n', encoding="utf-8")
    result = CliRunner().invoke(
        app, ["check", "all", str(docs), "--no-header", "--quiet"], catch_exceptions=False
    )
    assert result.exit_code == 2, f"the security tier must still own exit 2: {result.output}"


class TestTheRemapDoesNotEscapeZenzic:
    """Importing a library must not change how somebody else's program exits."""

    @staticmethod
    def _unrelated_click_app_usage_exit() -> int | str | None:
        @click.command()
        @click.option("--name", required=True)
        def other_app(name: str) -> None:  # pragma: no cover - never reaches the body
            click.echo(name)

        try:
            other_app.main(["--nope"], standalone_mode=True)
        except SystemExit as exc:
            return exc.code
        return None

    def test_importing_zenzic_leaves_click_untouched(self) -> None:
        """`zenzic.main` is already imported by this module's own import block."""
        assert click.exceptions.UsageError.exit_code == 2

    def test_importing_zenzic_leaves_typers_vendored_click_untouched(self) -> None:
        from typer import _click as typer_click

        assert typer_click.exceptions.UsageError.exit_code == 2

    def test_an_unrelated_click_app_still_exits_2(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = self._unrelated_click_app_usage_exit()
        capsys.readouterr()
        assert code == 2, "importing zenzic changed an unrelated Click app's exit code"

    def test_still_2_after_zenzic_has_run_its_entry_point(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The scope must be released, not merely narrowed."""
        _run_entry_point(["definitely-not-a-command"], monkeypatch)
        code = self._unrelated_click_app_usage_exit()
        capsys.readouterr()
        assert code == 2

    def test_the_mechanism_really_is_active_inside_the_scope(self) -> None:
        """Negative control: without this, the tests above would pass vacuously."""
        with _usage_errors_exit_1():
            assert click.exceptions.UsageError.exit_code == 1
        assert click.exceptions.UsageError.exit_code == 2

    def test_the_scope_is_released_even_when_the_body_raises(self) -> None:
        with pytest.raises(RuntimeError):
            with _usage_errors_exit_1():
                raise RuntimeError("boom")
        assert click.exceptions.UsageError.exit_code == 2
