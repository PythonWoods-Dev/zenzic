# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``check <file>``'s text output must label the Suppression Audit footer's
scope, since the number itself stays project-wide by design.

Regression for: after `V031_SINGLE_FILE_DQS_SCOPE_AMBIGUITY` correctly made
the DQS score line file-scoped, the `🔒 Suppression Audit: N/cap` footer
directly below it remained silently project-wide with no label — so a
single-file scan showed two adjacent lines with different, unstated scopes.
The CAP number itself is intentionally NOT rescoped (the suppression cap is
a project-level governance ceiling, not a per-file concept) — only the
missing label is fixed here.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.main import app


runner = CliRunner()


def _make_sandbox(tmp_path: Path) -> tuple[Path, Path]:
    toml = tmp_path / ".zenzic.toml"
    toml.write_text(
        textwrap.dedent("""\
            docs_dir = "docs"

            [build_context]
            engine = "standalone"
        """),
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "suppressed.md").write_text(
        textwrap.dedent("""\
            # Page With a Suppression

            This page carries an inline suppression directive on a
            forbidden-brand mention, giving the project real technical debt
            that a single-file scan of an unrelated page should never
            silently attribute to itself without saying so.

            Legacy brand mention. <!-- zenzic:ignore: Z601 - historical reference -->
        """),
        encoding="utf-8",
    )
    clean = docs / "clean.md"
    clean.write_text(
        textwrap.dedent("""\
            # Unrelated Clean Page

            This page has no suppressions of its own — it exists purely to
            prove the footer beneath it is correctly labeled as describing
            the whole project's debt, not this page's own debt.
        """),
        encoding="utf-8",
    )
    return tmp_path, clean


def test_single_file_footer_labels_project_wide_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scanning clean.md alone must show the footer's project-wide scope
    explicitly, since the number shown still reflects the whole project."""
    root, clean_file = _make_sandbox(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["check", "all", "docs/clean.md"])

    assert "project-wide" in result.stdout.lower(), (
        f"A single-file scan's Suppression Audit footer still shows a "
        f"project-wide number (inherited from suppressed.md elsewhere) but "
        f"does not label it as such — a user cannot tell this number isn't "
        f"about clean.md. Full stdout: {result.stdout}"
    )


def test_full_project_scan_footer_unlabeled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression guard: a full-project scan (no target) must NOT gain a
    spurious per-file/project-wide label — the label is only meaningful
    (and only added) when a single-file target narrows other output."""
    root, _clean_file = _make_sandbox(tmp_path)
    monkeypatch.chdir(root)

    result = runner.invoke(app, ["check", "all"])

    assert "project-wide" not in result.stdout.lower(), (
        f"Full-project scan's footer should not carry a scope label — there "
        f"is no scope mismatch to disambiguate when no single-file target "
        f"was given. Full stdout: {result.stdout}"
    )
