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
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.main import app


_SECRET = "AKIA" + "IOSFODNN7EXAMPLE"
_PROSE = "Prose long enough to clear the minimum word-count check comfortably here."


@pytest.mark.parametrize(
    ("label", "argv"),
    [
        ("unknown option", ["check", "all", "--definitely-not-a-flag"]),
        ("unknown command", ["definitely-not-a-command"]),
        ("unknown subcommand", ["check", "definitely-not-a-subcommand"]),
    ],
)
def test_usage_errors_exit_1_not_2(label: str, argv: list[str]) -> None:
    result = CliRunner().invoke(app, argv)
    assert result.exit_code == 1, (
        f"{label} exited {result.exit_code}; exit 2 is reserved for the security "
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
