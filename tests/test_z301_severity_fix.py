# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for V031_Z301_SEVERITY_FIX_AND_BACKLOG_SEQUENCING.

Before this fix, ``Z301`` (DANGLING_REF) was classified as ``"warning"`` in
``src/zenzic/core/codes.py``'s ``CODE_DEFINITIONS`` (the declared single
source of truth), but ``src/zenzic/core/scanner.py`` hardcoded
``is_warning=False`` when constructing the ``ReferenceFinding`` for a
dangling reference — a documented, deliberate override in
``ReferenceFinding``'s own docstring, but one that directly contradicted
``codes.py``. Per the Tier-0 Exit Code Contract ("Exit 1: Quality findings
— Errors, or Warnings under ``--strict``"), this meant every dangling
reference hard-failed a plain ``zenzic check`` run with no ``--strict``
flag, verified via live reproduction before this fix.

The Tech Lead's decision: ``codes.py``'s "warning" classification is
authoritative. ``scanner.py``'s override is removed so Z301 behaves like
any other warning-level finding (``--strict``-gated), matching its
siblings Z302/Z303, which never had this override.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
from typer.testing import CliRunner

from zenzic.main import app


runner = CliRunner()


@pytest.fixture
def dangling_ref_sandbox(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / ".zenzic.toml").write_text(
        'docs_dir = "docs"\n\n[build_context]\nengine = "standalone"\n',
        encoding="utf-8",
    )
    (tmp_path / "docs" / "index.md").write_text(
        dedent("""\
            # Welcome

            See the [Installation Guide][install-guide] for setup details. Every
            contributor is expected to follow the standard workflow described there
            before opening a pull request against the main branch of this project.
            This page also links onward to a second page with further context.

            Also check the [Guide](guide.md) for more context on the overall setup.
        """),
        encoding="utf-8",
    )
    (tmp_path / "docs" / "guide.md").write_text(
        dedent("""\
            # Guide

            This is a secondary page with enough words to clear the short-content
            threshold comfortably, and it links back to the index page so that
            neither page ends up as an unreachable dead end in the navigation graph.

            See the [index page](index.md) for the starting point of this project.
        """),
        encoding="utf-8",
    )
    return tmp_path


def test_dangling_ref_does_not_hard_fail_without_strict(
    dangling_ref_sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lone Z301 (warning-level per codes.py) must not cause Exit 1 unless
    --strict is passed, matching the Tier-0 Exit Code Contract."""
    monkeypatch.chdir(dangling_ref_sandbox)

    result = runner.invoke(app, ["check", "all", "--no-header"])

    assert result.exit_code == 0, (
        f"A dangling reference is a warning-level finding (codes.py: Z301 -> "
        f"'warning') and must not hard-fail a non---strict run. "
        f"stdout:\n{result.stdout}"
    )
    assert "[Z301]" in result.stdout
    assert "0 errors" in result.stdout
    assert "1 warning" in result.stdout


def test_dangling_ref_fails_under_strict(
    dangling_ref_sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same warning-level finding must still gate the build under --strict,
    proving this is a --strict-gated warning, not a silently-ignored one."""
    monkeypatch.chdir(dangling_ref_sandbox)

    result = runner.invoke(app, ["check", "all", "--strict", "--no-header"])

    assert result.exit_code == 1, (
        f"A warning-level Z301 finding must fail the build under --strict. stdout:\n{result.stdout}"
    )


def test_dangling_ref_appears_in_json_references(
    dangling_ref_sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The --format json payload's `references` array must still include the
    Z301 finding (unaffected by the severity fix -- this field is populated
    regardless of severity, per V031_CHECK_ALL_JSON_LEGACY_REFERENCES_EMPTY)."""
    monkeypatch.chdir(dangling_ref_sandbox)

    result = runner.invoke(app, ["check", "all", "--format", "json", "--no-header"])
    payload = json.loads(result.stdout)

    assert payload["security_breaches"] == 0, f"Full payload: {payload}"
    assert any("Z301" in entry for entry in payload["references"]), f"Full payload: {payload}"
