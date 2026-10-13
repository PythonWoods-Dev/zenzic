# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A `.gitignore` line must not silence the credential scanner.

``security_view()`` strips every user-configurable exclusion layer so the
security tier cannot be suppressed by configuration — but it retained the VCS
layer, on the stated rationale that "gitignored content is deliberately outside
the published corpus, so *everything that ships gets the secret scan*".

That rationale does not hold. ``pathspec`` implements gitignore *pattern
matching*; it does not implement git's rule that an already-tracked file is
never ignored. A one-line `.gitignore` addition therefore hides a file from
Zenzic while git keeps tracking it, so the file still ships and still renders —
the exact opposite of the boundary the docstring claims.

`.gitignore` is also user-editable and reviewer-invisible, which makes it a
suppression mechanism for a tier three separate code paths call
non-suppressible. It is now stripped from the security view like every other
user-controllable layer.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.main import app


_SECRET = "AKIA" + "IOSFODNN7EXAMPLE"
_PROSE = "Prose long enough to clear the minimum word-count check comfortably here."


def _project(tmp_path: Path, gitignore: str | None) -> None:
    (tmp_path / "mkdocs.yml").write_text("site_name: Demo\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n', encoding="utf-8")
    docs = tmp_path / "docs"
    (docs / "vendor").mkdir(parents=True)
    (docs / "index.md").write_text(f"# Home\n\n{_PROSE}\n", encoding="utf-8")
    (docs / "vendor" / "creds.md").write_text(
        f'# V\n\n{_PROSE}\n\naws_key = "{_SECRET}"\n', encoding="utf-8"
    )
    if gitignore is not None:
        (tmp_path / ".gitignore").write_text(gitignore, encoding="utf-8")


def _check(tmp_path: Path) -> int:
    return (
        CliRunner()
        .invoke(
            app,
            ["check", "all", str(tmp_path / "docs"), "--no-header", "--quiet"],
            catch_exceptions=False,
        )
        .exit_code
    )


@pytest.mark.parametrize(
    ("label", "gitignore"),
    [
        ("directory pattern", "vendor/\n"),
        ("bare filename", "creds.md\n"),
        ("glob", "*.md\n"),
        ("path pattern", "docs/vendor/**\n"),
    ],
)
def test_gitignore_cannot_hide_a_credential(tmp_path: Path, label: str, gitignore: str) -> None:
    _project(tmp_path, gitignore)
    assert _check(tmp_path) == 2, (
        f"a .gitignore {label} silenced the credential scanner — a tracked, shipped "
        "file was hidden from a tier that is never suppressible"
    )


def test_control_without_gitignore_also_reports(tmp_path: Path) -> None:
    _project(tmp_path, None)
    assert _check(tmp_path) == 2


def test_guard_scan_is_equally_unfooled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The pre-commit gate is the boundary that keeps a leak out of history."""
    _project(tmp_path, "vendor/\n")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["guard", "scan"], catch_exceptions=False)
    assert result.exit_code == 2, f"guard scan was blinded by .gitignore:\n{result.output}"


def test_quality_tier_still_honours_gitignore(tmp_path: Path) -> None:
    """The negative control: only the security tier ignores VCS scoping.

    A gitignored file with a purely quality defect must stay excluded, or this
    fix would have turned `.gitignore` into a no-op for the whole engine.
    """
    (tmp_path / "mkdocs.yml").write_text("site_name: Demo\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n', encoding="utf-8")
    docs = tmp_path / "docs"
    (docs / "vendor").mkdir(parents=True)
    (docs / "index.md").write_text(f"# Home\n\n{_PROSE}\n", encoding="utf-8")
    (docs / "vendor" / "page.md").write_text(
        f"# V\n\n{_PROSE}\n\n[broken](./nope.md)\n", encoding="utf-8"
    )
    (tmp_path / ".gitignore").write_text("vendor/\n", encoding="utf-8")
    assert _check(tmp_path) == 0, "a gitignored file's quality findings leaked into the report"
