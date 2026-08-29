# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for Zenzic CLI commands."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import ANY, patch

import pytest
from typer.testing import CliRunner

from zenzic.core.validator import LinkError, SnippetError
from zenzic.main import app, cli_main
from zenzic.models.config import ZenzicConfig


runner = CliRunner()

_ROOT = Path("/fake/repo")
_CFG = ZenzicConfig()


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------


def test_cli_main_calls_app() -> None:
    with patch("zenzic.main.app") as mock_app:
        cli_main()
        mock_app.assert_called_once()


# ---------------------------------------------------------------------------
# help
# ---------------------------------------------------------------------------


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Engine-agnostic" in result.stdout


# ---------------------------------------------------------------------------
# check links
# ---------------------------------------------------------------------------


@patch("zenzic.cli._command_setup.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, False))
@patch("zenzic.cli._check.validate_links_structured", return_value=[])
def test_check_links_ok(_links, _cfg, _root) -> None:
    result = runner.invoke(app, ["check", "links"])
    assert result.exit_code == 0
    assert "ZENZIC" in (result.stdout + result.stderr)
    assert "No broken links found." in result.stdout


@patch("zenzic.cli._command_setup.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, False))
@patch(
    "zenzic.cli._check.validate_links_structured",
    return_value=[
        LinkError(
            file_path=_ROOT / "docs" / "index.md",
            line_no=1,
            message="index.md:1: broken link 'foo.md' (is not found)",
            source_line="[foo](foo.md)",
            error_type="Z104",
        )
    ],
)
def test_check_links_with_errors(_links, _cfg, _root) -> None:
    result = runner.invoke(app, ["check", "links"])
    assert result.exit_code == 1
    assert "ZENZIC" in (result.stdout + result.stderr)
    assert "Z104" in result.stdout or "error" in result.stdout.lower()


@patch("zenzic.cli._command_setup.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, False))
@patch("zenzic.cli._check.validate_links_structured", return_value=[])
def test_check_links_strict_passes_flag(mock_links, _cfg, _root) -> None:
    runner.invoke(app, ["check", "links", "--strict"])
    # reports=/ext_errors= were added so check_links can reuse the single
    # scan_docs_references() pass (and its credential-scan results) instead
    # of discarding them -- see V031_EXIT2_WIRING_AND_Z406_ADAPTER_AGNOSTICISM_CHECK.
    mock_links.assert_called_once_with(
        (_ROOT / "docs").resolve(),
        ANY,
        repo_root=_ROOT,
        config=_CFG,
        strict=True,
        locale_roots=None,
        check_external=True,
        reports=ANY,
        ext_errors=ANY,
    )


@patch("zenzic.cli._command_setup.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, False))
@patch(
    "zenzic.cli._check.validate_links_structured",
    return_value=[
        LinkError(
            file_path=_ROOT / "docs" / "index.md",
            line_no=2,
            message="index.md:2: '../../../../etc/passwd' resolves outside the docs directory",
            source_line="[escape](../../../../etc/passwd)",
            error_type="Z203",
        )
    ],
)
def test_check_links_system_path_traversal_exits_3(_links, _cfg, _root) -> None:
    """check links exits with code 3 when a system-path traversal is found."""
    result = runner.invoke(app, ["check", "links"])
    assert result.exit_code == 3


@patch("zenzic.cli._command_setup.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, False))
@patch(
    "zenzic.cli._check.validate_links_structured",
    return_value=[
        LinkError(
            file_path=_ROOT / "docs" / "index.md",
            line_no=2,
            message="index.md:2: '../../outside.md' resolves outside the docs directory",
            source_line="[escape](../../outside.md)",
            error_type="Z202",
        )
    ],
)
def test_check_links_boundary_traversal_exits_1(_links, _cfg, _root) -> None:
    """check links exits with code 1 for a non-system path traversal (no regression)."""
    result = runner.invoke(app, ["check", "links"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# check orphans
# ---------------------------------------------------------------------------


def test_cli_check_orphans_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".zenzic.toml").touch()  # engine-neutral root marker
    monkeypatch.chdir(repo)
    result = runner.invoke(app, ["check", "orphans"])
    assert result.exit_code == 0
    assert "ZENZIC" in (result.stdout + result.stderr)
    assert "No orphan pages found." in result.stdout


@patch("zenzic.cli._command_setup.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._check.find_orphans", return_value=[Path("orphan.md")])
def test_check_orphans_with_orphans(_orphans, _cfg, _root) -> None:
    result = runner.invoke(app, ["check", "orphans"])
    assert result.exit_code == 1
    assert "ZENZIC" in (result.stdout + result.stderr)
    assert "Z402" in result.stdout


# ---------------------------------------------------------------------------
# check snippets
# ---------------------------------------------------------------------------


@patch("zenzic.cli._command_setup.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._check.validate_snippets", return_value=[])
def test_check_snippets_ok(_snip, _cfg, _root) -> None:
    result = runner.invoke(app, ["check", "snippets"])
    assert result.exit_code == 0
    assert "ZENZIC" in (result.stdout + result.stderr)
    assert "All code snippets are syntactically valid." in result.stdout


@patch("zenzic.cli._command_setup.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch(
    "zenzic.cli._check.validate_snippets",
    return_value=[
        SnippetError(
            file_path=Path("api.md"),
            line_no=5,
            message="SyntaxError in Python snippet — invalid syntax",
        )
    ],
)
def test_check_snippets_with_errors(_snip, _cfg, _root) -> None:
    # Z503 is "warning" per codes.py's CODE_DEFINITIONS (the SSoT) -- it used
    # to hardcode severity="error" here, which caused every snippet syntax
    # error to hard-fail unconditionally (fixed in
    # V031_SEVERITY_HARDCODE_ARCHITECTURAL_REMEDIATION, same bug shape as
    # Z301/Z406). `check snippets` originally had no --strict flag at all,
    # so a warning could never be promoted to a hard failure on this
    # subcommand -- that gap is closed in
    # V031_RULES_PY_STRUCTURAL_FIX_AND_STRICT_FLAG_GAP, verified below.
    result = runner.invoke(app, ["check", "snippets"])
    assert result.exit_code == 0
    assert "ZENZIC" in (result.stdout + result.stderr)
    assert "Z503" in result.stdout

    result_strict = runner.invoke(app, ["check", "snippets", "--strict"])
    assert result_strict.exit_code == 1
    assert "Z503" in result_strict.stdout


# ---------------------------------------------------------------------------
# check assets
# ---------------------------------------------------------------------------


@patch("zenzic.cli._check.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._check.find_unused_assets", return_value=[])
def test_check_assets_ok(_assets, _cfg, _root) -> None:
    result = runner.invoke(app, ["check", "assets"])
    assert result.exit_code == 0
    assert "ZENZIC" in (result.stdout + result.stderr)
    assert "No unused assets found." in result.stdout


@patch("zenzic.cli._check.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._check.find_unused_assets", return_value=[Path("assets/unused.png")])
def test_check_assets_with_unused(_assets, _cfg, _root) -> None:
    result = runner.invoke(app, ["check", "assets"])
    assert result.exit_code == 1
    assert "ZENZIC" in (result.stdout + result.stderr)
    assert "Z405" in result.stdout


# ---------------------------------------------------------------------------
# check placeholders
# ---------------------------------------------------------------------------


@patch("zenzic.cli._command_setup.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._check.scan_docs_references", return_value=([], []))
def test_check_placeholders_ok(_ph, _cfg, _root) -> None:
    result = runner.invoke(app, ["check", "placeholders"])
    assert result.exit_code == 0
    assert "ZENZIC" in (result.stdout + result.stderr)
    assert "No placeholder stubs found." in result.stdout


@patch("zenzic.cli._command_setup.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._check.scan_docs_references")
def test_check_placeholders_with_findings(_refs, _cfg, _root) -> None:
    from zenzic.core.rules import RuleFinding
    from zenzic.models.references import IntegrityReport

    rep = IntegrityReport(file_path=Path("stub.md"), score=100.0)
    rep.rule_findings = [
        RuleFinding(
            rule_id="Z502",
            severity="warning",
            file_path=Path("stub.md"),
            line_no=1,
            message="5 words",
        )
    ]
    _refs.return_value = ([rep], [])

    # check_placeholders used to hardcode strict=True unconditionally --
    # every warning-level finding hard-failed even without --strict, and the
    # reporter would misleadingly print "Warnings promoted to errors via
    # --strict flag" even though no such flag was passed. Fixed in
    # V031_RULES_PY_STRUCTURAL_FIX_AND_STRICT_FLAG_GAP: strict is now a real,
    # gated flag, default False, consistent with check_links/check_all.
    result = runner.invoke(app, ["check", "placeholders"])
    assert result.exit_code == 0
    assert "ZENZIC" in (result.stdout + result.stderr)
    assert "Z502" in result.stdout

    result_strict = runner.invoke(app, ["check", "placeholders", "--strict"])
    assert result_strict.exit_code == 1
    assert "Z502" in result_strict.stdout


# ---------------------------------------------------------------------------
# check all — JSON
# ---------------------------------------------------------------------------


def test_cli_check_all_json_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".zenzic.toml").touch()  # engine-neutral root marker
    (repo / "docs").mkdir()
    monkeypatch.chdir(repo)
    result = runner.invoke(app, ["check", "all", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert set(data) == {
        "links",
        "orphans",
        "snippets",
        "unused_assets",
        "nav_contract",
        "references",
        "security_breaches",
        "security_incidents",
        "suppression_count",
        "suppression_cap",
        "suppression_debt_pts",
        "debt_status",
    }
    assert data["security_breaches"] == 0
    assert data["security_incidents"] == 0
    assert data["suppression_count"] == 0
    assert data["suppression_cap"] == 30
    assert data["suppression_debt_pts"] == 0
    assert data["debt_status"] == "CLEAN"


@patch("zenzic.cli._check.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch(
    "zenzic.cli._check.validate_links_structured",
    return_value=[
        LinkError(
            file_path=_ROOT / "docs" / "index.md",
            line_no=1,
            message="index.md:1: broken link",
        )
    ],
)
@patch("zenzic.cli._check.find_orphans", return_value=[])
@patch("zenzic.cli._check.validate_snippets", return_value=[])
@patch("zenzic.cli._check.find_unused_assets", return_value=[])
@patch("zenzic.cli._check.check_nav_contract", return_value=[])
@patch("zenzic.cli._check.scan_docs_references", return_value=([], []))
def test_check_all_json_with_errors(
    _refs, _nav, _assets, _snip, _orphans, _links, _cfg, _root
) -> None:
    result = runner.invoke(app, ["check", "all", "--format", "json"])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert len(data["links"]) == 1


# ---------------------------------------------------------------------------
# check all — text mode
# ---------------------------------------------------------------------------


@patch("zenzic.cli._shared._count_docs_assets", return_value=(5, 0))
@patch("zenzic.cli._check.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._check.validate_links_structured", return_value=[])
@patch("zenzic.cli._check.find_orphans", return_value=[])
@patch("zenzic.cli._check.validate_snippets", return_value=[])
@patch("zenzic.cli._check.find_unused_assets", return_value=[])
@patch("zenzic.cli._check.check_nav_contract", return_value=[])
@patch("zenzic.cli._check.scan_docs_references", return_value=([], []))
def test_check_all_text_ok(
    _refs, _nav, _assets, _snip, _orphans, _links, _cfg, _root, _count
) -> None:
    result = runner.invoke(app, ["check", "all"])
    assert result.exit_code == 0
    assert "Analysis complete" in result.stdout or "No broken links" in result.stdout


@patch("zenzic.cli._shared._count_docs_assets", return_value=(5, 2))
@patch("zenzic.cli._check.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch(
    "zenzic.cli._check.validate_links_structured",
    return_value=[
        LinkError(
            file_path=_ROOT / "docs" / "index.md",
            line_no=1,
            message="index.md:1: broken link",
        )
    ],
)
@patch("zenzic.cli._check.find_orphans", return_value=[Path("orphan.md")])
@patch(
    "zenzic.cli._check.validate_snippets",
    return_value=[SnippetError(file_path=Path("api.md"), line_no=5, message="SyntaxError")],
)
@patch("zenzic.cli._check.find_unused_assets", return_value=[Path("assets/unused.png")])
@patch("zenzic.cli._check.check_nav_contract", return_value=[])
@patch("zenzic.cli._check.scan_docs_references")
def test_check_all_text_with_all_errors(
    _refs, _nav, _assets, _snip, _orphans, _links, _cfg, _root, _count
) -> None:
    from zenzic.core.rules import RuleFinding
    from zenzic.models.references import IntegrityReport

    rep = IntegrityReport(file_path=Path("stub.md"), score=100.0)
    rep.rule_findings = [
        RuleFinding(
            rule_id="Z501",
            severity="warning",
            file_path=Path("stub.md"),
            line_no=1,
            message="short-content",
        )
    ]
    _refs.return_value = ([rep], [])

    result = runner.invoke(app, ["check", "all"])
    assert result.exit_code == 1
    assert "FAILED" in result.stdout
    assert "error" in result.stdout.lower()
    assert "orphan.md" in result.stdout
    assert "SyntaxError" in result.stdout
    assert "unused.png" in result.stdout or "ASSET" in result.stdout


# ---------------------------------------------------------------------------
# check all — quiet mode
# ---------------------------------------------------------------------------


@patch("zenzic.cli._check.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._check.validate_links_structured", return_value=[])
@patch("zenzic.cli._check.find_orphans", return_value=[])
@patch("zenzic.cli._check.validate_snippets", return_value=[])
@patch("zenzic.cli._check.find_unused_assets", return_value=[])
@patch("zenzic.cli._check.check_nav_contract", return_value=[])
@patch("zenzic.cli._check.scan_docs_references", return_value=([], []))
def test_check_all_quiet_ok(_refs, _nav, _assets, _snip, _orphans, _links, _cfg, _root) -> None:
    result = runner.invoke(app, ["check", "all", "--quiet"])
    assert result.exit_code == 0
    # Quiet mode produces no output when clean
    assert "zenzic" not in result.stdout.lower() or result.stdout.strip() == ""


@patch("zenzic.cli._check.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch(
    "zenzic.cli._check.validate_links_structured",
    return_value=[
        LinkError(
            file_path=_ROOT / "docs" / "index.md",
            line_no=1,
            message="broken link",
        )
    ],
)
@patch("zenzic.cli._check.find_orphans", return_value=[])
@patch("zenzic.cli._check.validate_snippets", return_value=[])
@patch("zenzic.cli._check.find_unused_assets", return_value=[])
@patch("zenzic.cli._check.check_nav_contract", return_value=[])
@patch("zenzic.cli._check.scan_docs_references", return_value=([], []))
def test_check_all_quiet_with_errors(
    _refs, _nav, _assets, _snip, _orphans, _links, _cfg, _root
) -> None:
    result = runner.invoke(app, ["check", "all", "--quiet"])
    assert result.exit_code == 1
    assert "error" in result.stdout.lower()


# ---------------------------------------------------------------------------
# check all — ci and only flags
# ---------------------------------------------------------------------------


@patch("zenzic.cli._check.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch(
    "zenzic.cli._check.validate_links_structured",
    return_value=[
        LinkError(
            file_path=_ROOT / "docs" / "index.md",
            line_no=1,
            message="broken link",
            error_type="Z104",
        )
    ],
)
@patch("zenzic.cli._check.find_orphans", return_value=[])
@patch("zenzic.cli._check.validate_snippets", return_value=[])
@patch("zenzic.cli._check.find_unused_assets", return_value=[])
@patch("zenzic.cli._check.check_nav_contract", return_value=[])
@patch("zenzic.cli._check.scan_docs_references", return_value=([], []))
def test_check_all_ci_forces_github_annotations(
    _refs, _nav, _assets, _snip, _orphans, _links, _cfg, _root
) -> None:
    result = runner.invoke(app, ["check", "all", "--ci"])
    assert result.exit_code == 1
    # Check that it outputs github-annotations format.
    # On Windows with mock absolute paths without drive letters, relpath may fallback to absolute.
    out_normalized = result.stdout.replace("\\", "/")
    assert "::error file=" in out_normalized
    assert "docs/index.md,line=1,title=Z104::broken link" in out_normalized


@patch("zenzic.cli._check.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch(
    "zenzic.cli._check.validate_links_structured",
    return_value=[
        LinkError(
            file_path=_ROOT / "docs" / "index.md",
            line_no=1,
            message="broken link",
            error_type="Z104",
        ),
        LinkError(
            file_path=_ROOT / "docs" / "other.md",
            line_no=2,
            message="another link",
            error_type="Z101",
        ),
    ],
)
@patch("zenzic.cli._check.find_orphans", return_value=[Path("orphan.md")])
@patch("zenzic.cli._check.validate_snippets", return_value=[])
@patch("zenzic.cli._check.find_unused_assets", return_value=[])
@patch("zenzic.cli._check.check_nav_contract", return_value=[])
@patch("zenzic.cli._check.scan_docs_references", return_value=([], []))
def test_check_all_only_filters_findings(
    _refs, _nav, _assets, _snip, _orphans, _links, _cfg, _root
) -> None:
    result = runner.invoke(app, ["check", "all", "--format", "json", "--only", "Z104"])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert len(data["links"]) == 1
    assert "broken link" in data["links"][0]
    # Orphans (Z402) should be filtered out because only Z104 is allowed
    assert len(data["orphans"]) == 0


# ---------------------------------------------------------------------------
# check all — strict gate on warnings
# ---------------------------------------------------------------------------


@patch("zenzic.cli._shared._count_docs_assets", return_value=(5, 0))
@patch("zenzic.cli._check.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._check.validate_links_structured", return_value=[])
@patch("zenzic.cli._check.find_orphans", return_value=[])
@patch("zenzic.cli._check.validate_snippets", return_value=[])
@patch("zenzic.cli._check.find_unused_assets", return_value=[])
@patch("zenzic.cli._check.check_nav_contract", return_value=[])
@patch("zenzic.cli._check.scan_docs_references")
def test_check_all_strict_fails_on_warnings_only(
    mock_refs, _nav, _assets, _snip, _orphans, _links, _cfg, _root, _count
) -> None:
    """--strict must exit 1 even when only warnings (no hard errors) exist."""
    from zenzic.models.references import IntegrityReport, ReferenceFinding

    finding = ReferenceFinding(
        file_path=Path("docs/guide.md"),
        line_no=10,
        issue="DEAD_DEF",
        detail="[unused]: never referenced",
        is_warning=True,
    )
    report = IntegrityReport(file_path=Path("docs/guide.md"), score=90.0)
    report.findings = [finding]
    mock_refs.return_value = ([report], [])

    result = runner.invoke(app, ["check", "all", "--strict"])
    assert result.exit_code == 1


@patch("zenzic.cli._check.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._check.validate_links_structured", return_value=[])
@patch("zenzic.cli._check.find_orphans", return_value=[])
@patch("zenzic.cli._check.validate_snippets", return_value=[])
@patch("zenzic.cli._check.find_unused_assets", return_value=[])
@patch("zenzic.cli._check.check_nav_contract", return_value=[])
@patch("zenzic.cli._check.scan_docs_references")
def test_check_all_no_strict_passes_on_warnings_only(
    mock_refs, _nav, _assets, _snip, _orphans, _links, _cfg, _root
) -> None:
    """Without --strict, warnings alone must NOT trigger exit 1."""
    from zenzic.models.references import IntegrityReport, ReferenceFinding

    finding = ReferenceFinding(
        file_path=Path("docs/guide.md"),
        line_no=10,
        issue="DEAD_DEF",
        detail="[unused]: never referenced",
        is_warning=True,
    )
    report = IntegrityReport(file_path=Path("docs/guide.md"), score=90.0)
    report.findings = [finding]
    mock_refs.return_value = ([report], [])

    result = runner.invoke(app, ["check", "all"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# check all — target argument (file and directory mode)
# ---------------------------------------------------------------------------


@patch("zenzic.cli._check.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
def test_check_all_target_not_found(_cfg, _root) -> None:
    """Non-existent target must exit 1 with an error message."""
    result = runner.invoke(app, ["check", "all", "nonexistent.md"])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()
    assert "nonexistent.md" in result.stdout


def test_check_all_target_single_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Single .md file target: findings filtered, banner shows 1 file."""
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / ".zenzic.toml").touch()
    _body = "word " * 60
    (repo / "docs" / "index.md").write_text(f"# Hello\n\n{_body}\n")
    (repo / "docs" / "other.md").write_text(f"# Other\n\n{_body}\n")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["check", "all", "docs/index.md"])
    assert result.exit_code == 0
    assert "1 file" in result.stdout
    assert "other.md" not in result.stdout


def test_check_all_target_file_outside_docs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """File outside docs_dir (e.g. README.md): config patched, exit 0."""
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / ".zenzic.toml").touch()
    _body = "word " * 60
    (repo / "docs" / "index.md").write_text(f"# Hello\n\n{_body}\n")
    (repo / "README.md").write_text(f"# Project\n\n{_body}\n")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["check", "all", "README.md"])
    assert result.exit_code == 0
    assert "1 file" in result.stdout
    assert "README.md" in result.stdout
    assert "index.md" not in result.stdout


def test_check_all_target_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Directory target: config patched to that dir, full scan within it."""
    repo = tmp_path / "repo"
    (repo / "content").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / ".zenzic.toml").touch()
    _body = "word " * 60
    (repo / "content" / "page.md").write_text(f"# Page\n\n{_body}\n")
    (repo / "docs" / "other.md").write_text(f"# Other\n\n{_body}\n")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["check", "all", "content"])
    assert result.exit_code == 0
    assert "./content/" in result.stdout
    assert "other.md" not in result.stdout


def test_check_all_external_docs_root_not_blocked_by_boundary_check(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The External Audit (CEO-043): explicit path outside CWD repo root must not trigger path traversal guard (Exit 3).

    Simulates: `zenzic check all ../zenzic-doc` from inside a sibling project.
    The path traversal guard must guard escapes FROM the target, not the location OF the target.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".zenzic.toml").touch()

    ext_docs = tmp_path / "ext_docs"
    ext_docs.mkdir()
    (ext_docs / "index.md").write_text("# External Docs\n\n" + "word " * 60)

    monkeypatch.chdir(repo)
    rel = os.path.relpath(ext_docs, repo)  # resolves to "../ext_docs"
    result = runner.invoke(app, ["check", "all", rel])

    assert result.exit_code != 3, (
        f"Path traversal guard incorrectly blocked an explicit external path.\n{result.output}"
    )


# ---------------------------------------------------------------------------
# ZenzicReporter unit tests
# ---------------------------------------------------------------------------


class TestZenzicReporter:
    """Unit tests for the Zenzic Report Engine."""

    def test_render_no_findings(self) -> None:
        from io import StringIO

        from rich.console import Console

        from zenzic.core.reporter import ZenzicReporter

        buf = StringIO()
        con = Console(file=buf, highlight=False, no_color=True)
        reporter = ZenzicReporter(con, Path("/fake/docs"))
        errors, warnings = reporter.render(
            [], version="0.5.0a3", elapsed=1.0, docs_count=6, assets_count=4
        )
        assert errors == 0
        assert warnings == 0
        output = buf.getvalue()
        assert "auto" in output  # telemetry engine field
        assert "Analysis complete" in output

    def test_render_grouped_findings(self) -> None:
        from io import StringIO

        from rich.console import Console

        from zenzic.core.reporter import Finding, ZenzicReporter

        findings = [
            Finding("guide/index.md", 10, "LINK_ERROR", "error", "broken link"),
            Finding("guide/index.md", 20, "SNIPPET", "error", "syntax error"),
            Finding("about.md", 5, "ORPHAN", "warning", "not in nav"),
        ]
        buf = StringIO()
        con = Console(file=buf, highlight=False, no_color=True)
        reporter = ZenzicReporter(con, Path("/fake/docs"))
        errors, warnings = reporter.render(
            findings, version="0.5.0a3", elapsed=0.5, docs_count=5, assets_count=0
        )
        assert errors == 2
        assert warnings == 1
        output = buf.getvalue()
        assert "guide/index.md" in output
        assert "about.md" in output
        assert "2 errors" in output
        assert "1 warning" in output

    def test_render_quiet_no_findings(self) -> None:
        from io import StringIO

        from rich.console import Console

        from zenzic.core.reporter import ZenzicReporter

        buf = StringIO()
        con = Console(file=buf, highlight=False, no_color=True)
        reporter = ZenzicReporter(con, Path("/fake/docs"))
        errors, warnings = reporter.render_quiet([])
        assert errors == 0
        assert warnings == 0
        assert buf.getvalue().strip() == ""

    def test_render_quiet_with_findings(self) -> None:
        from io import StringIO

        from rich.console import Console

        from zenzic.core.reporter import Finding, ZenzicReporter

        findings = [
            Finding("x.md", 1, "E001", "error", "bad"),
            Finding("y.md", 2, "W001", "warning", "meh"),
        ]
        buf = StringIO()
        con = Console(file=buf, highlight=False, no_color=True)
        reporter = ZenzicReporter(con, Path("/fake/docs"))
        errors, warnings = reporter.render_quiet(findings)
        assert errors == 1
        assert warnings == 1
        assert "1 error" in buf.getvalue()
        assert "1 warning" in buf.getvalue()

    def test_render_security_breach_is_counted_in_summary(self) -> None:
        from io import StringIO

        from rich.console import Console

        from zenzic.core.reporter import Finding, ZenzicReporter

        findings = [
            Finding(
                "docs/leaky.md",
                42,
                "Z201",
                "security_breach",
                "Secret detected (github-token) — rotate immediately.",
                source_line='token = "ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"',
                match_text="ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            )
        ]
        buf = StringIO()
        con = Console(file=buf, highlight=False, no_color=True)
        reporter = ZenzicReporter(con, Path("/fake/docs"))
        errors, warnings = reporter.render(
            findings, version="0.5.0a3", elapsed=0.2, docs_count=1, assets_count=0
        )
        assert errors == 0
        assert warnings == 0
        output = buf.getvalue()
        assert "SECURITY BREACH DETECTED" in output
        assert "security breach" in output
        assert "file impacted" in output
        assert "Exit code 2 is mandatory" in output
        # Z201 must show Credential label (obfuscated), NOT Term label
        assert "Credential:" in output
        assert "Rotate this credential immediately" in output
        assert "Term:" not in output

    def test_render_z204_shows_term_label_not_credential(self) -> None:
        """Z204 FORBIDDEN_TERM breach must show 'Term:' label and removal action, not credential rotation."""
        from io import StringIO

        from rich.console import Console

        from zenzic.core.reporter import Finding, ZenzicReporter

        findings = [
            Finding(
                "docs/leaked.md",
                7,
                "Z204",
                "security_breach",
                "Forbidden term detected — remove from documentation: 'openai'",
                source_line="This was generated by OpenAI tools.",
                match_text="openai",
            )
        ]
        buf = StringIO()
        con = Console(file=buf, highlight=False, no_color=True)
        reporter = ZenzicReporter(con, Path("/fake/docs"))
        reporter.render(findings, version="0.9.0", elapsed=0.1, docs_count=1, assets_count=0)
        output = buf.getvalue()
        assert "POLICY VIOLATION DETECTED" in output
        assert "SECURITY BREACH DETECTED" not in output
        assert "Term:" in output
        assert "openai" in output
        assert "Remove this term from the documentation" in output
        assert "forbidden_patterns" in output
        # Must NOT use credential labels for a forbidden-term finding
        assert "Credential:" not in output
        assert "Rotate this credential" not in output


# ---------------------------------------------------------------------------
# _finding_severity — Z2xx non-suppressible severity mapping
# ---------------------------------------------------------------------------


class TestFindingSeverityZ2xxMapping:
    """``_finding_severity()`` must map every code in the Tier-0 'Exit 2:
    never suppressible' set (Z201, Z204, Z205) to ``"security_breach"``.

    Z201/Z204 normally reach ``Finding.severity`` via the credential-scanner
    bridge (``_map_credential_to_finding``), which hardcodes
    ``severity="security_breach"`` and never calls ``_finding_severity()``.
    Z205 is detected by a rule check and reaches ``Finding.severity`` via
    ``_finding_severity(err.code)`` instead — which, before this fix, fell
    through to the raw ``CodeDefinition.severity`` catalog value (``"error"``)
    because only Z203 had a special case. This test targets the function
    directly, independent of which code path a given code takes today.
    """

    def test_z205_maps_to_security_breach(self) -> None:
        from zenzic.cli._check import _finding_severity

        assert _finding_severity("Z205") == "security_breach", (
            "Z205 FORBIDDEN_SCHEME is listed in the Tier-0 'Exit 2 — never "
            "suppressible' set alongside Z201/Z204 and must map to "
            "'security_breach', not the raw CodeDefinition severity ('error')."
        )

    def test_z203_still_maps_to_security_incident(self) -> None:
        """Regression guard: fixing Z205 must not disturb Z203's Exit 3 mapping."""
        from zenzic.cli._check import _finding_severity

        assert _finding_severity("Z203") == "security_incident"

    def test_z202_still_maps_to_plain_error(self) -> None:
        """Z202 PATH_TRAVERSAL is not in the Tier-0 Exit-2 set (only Z203 is
        Exit 3) — it must remain a plain 'error' (Exit 1), not be swept into
        this fix."""
        from zenzic.cli._check import _finding_severity

        assert _finding_severity("Z202") == "error"


# ---------------------------------------------------------------------------
# check references — rule_findings surfaced in CLI output
# ---------------------------------------------------------------------------


@patch("zenzic.cli._command_setup.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch(
    "zenzic.cli._check.scan_docs_references",
    return_value=([], []),
)
def test_check_references_ok(_scan, _cfg, _root) -> None:
    result = runner.invoke(app, ["check", "references"])
    assert result.exit_code == 0
    assert "ZENZIC" in (result.stdout + result.stderr)
    assert "All references resolved." in result.stdout


@patch("zenzic.cli._command_setup.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._check.scan_docs_references")
def test_check_references_rule_findings_surfaced(mock_scan, _cfg, _root) -> None:
    """rule_findings on IntegrityReport must appear in check references output."""
    from zenzic.core.rules import RuleFinding
    from zenzic.models.references import IntegrityReport

    rf = RuleFinding(
        file_path=Path("docs/guide.md"),
        line_no=12,
        rule_id="ZZ-NOCLICKHERE",
        message="Avoid generic link text.",
        severity="error",
    )
    report = IntegrityReport(file_path=Path("docs/guide.md"), score=100.0)
    report.rule_findings = [rf]
    mock_scan.return_value = ([report], [])

    result = runner.invoke(app, ["check", "references"])
    assert result.exit_code == 1
    assert "ZZ-NOCLICKHERE" in result.stdout
    assert "error" in result.stdout.lower()


# ---------------------------------------------------------------------------
# init --plugin
# ---------------------------------------------------------------------------


def test_init_plugin_scaffold_creates_expected_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init", "--plugin", "plugin-scaffold-demo"])
    assert result.exit_code == 0

    root = repo / "plugin-scaffold-demo"
    assert (root / "pyproject.toml").is_file()
    assert (root / "src" / "plugin_scaffold_demo" / "rules.py").is_file()
    assert (root / "docs" / "index.md").is_file()

    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert '[project.entry-points."zenzic.rules"]' in pyproject
    assert 'plugin-scaffold-demo = "plugin_scaffold_demo.rules:PluginScaffoldDemoRule"' in pyproject

    rules_py = (root / "src" / "plugin_scaffold_demo" / "rules.py").read_text(encoding="utf-8")
    assert "class PluginScaffoldDemoRule(BaseRule):" in rules_py


def test_init_plugin_scaffold_existing_dir_requires_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "plugin-scaffold-demo").mkdir()
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init", "--plugin", "plugin-scaffold-demo"])
    assert result.exit_code == 1
    assert "already exists" in result.stdout


# ---------------------------------------------------------------------------
# init — Smart Initialization (standalone vs pyproject.toml)
# ---------------------------------------------------------------------------


def test_init_standalone_creates_zenzic_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default init (no pyproject.toml present) creates .zenzic.toml."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    cfg = repo / ".zenzic.toml"
    assert cfg.is_file()
    content = cfg.read_text(encoding="utf-8")
    assert "# --- PROJECT IDENTITY ---" in content
    assert "[project_metadata]" in content
    assert '# release_name = "YOUR-RELEASE"' in content
    assert "suppression_cap = 30" in content
    assert "suppression_cap_fail_hard = true" in content
    assert "release-governance-protocol" in content

    local_cfg = repo / ".zenzic.local.toml"
    assert local_cfg.is_file()
    local_content = local_cfg.read_text(encoding="utf-8")
    assert "# ZENZIC LOCAL OVERRIDES" in local_content
    assert "This file is auto-generated" in local_content
    assert "forbidden_patterns = []" in local_content
    assert "suppression_cap_fail_hard = false" in local_content

    gitignore = repo / ".gitignore"
    assert gitignore.is_file()
    assert ".zenzic.local.toml" in gitignore.read_text(encoding="utf-8")

    # Panel must acknowledge both files
    assert ".zenzic.local.toml" in result.stdout
    assert "will be scaffolded next" in result.stdout


def test_init_standalone_detects_mkdocs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Engine auto-detection writes [build_context] when mkdocs.yml exists."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "mkdocs.yml").write_text("site_name: test\n", encoding="utf-8")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    content = (repo / ".zenzic.toml").read_text(encoding="utf-8")
    assert 'engine         = "mkdocs"' in content
    assert "(auto-detected)" in result.stdout


def test_init_standalone_warns_if_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse re-initialization when .zenzic.toml already exists."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / ".zenzic.toml").write_text("# existing\n", encoding="utf-8")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 1
    assert "Configuration already exists" in result.stdout
    normalized = " ".join(result.stdout.split())
    assert "Manual editing is required" in normalized


def test_init_standalone_force_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--force is blocked for configuration initialization."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init", "--force"])
    assert result.exit_code == 1
    assert "--force is not supported" in result.stdout


def test_init_standalone_discovers_project_name_from_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Init includes discovered project name as commented [project].name hint."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "castle-core"\n', encoding="utf-8")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init"], input="n\n")
    assert result.exit_code == 0

    content = (repo / ".zenzic.toml").read_text(encoding="utf-8")
    assert '# name = "castle-core"' in content


def test_init_standalone_discovers_project_name_from_package_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Init falls back to package.json name when pyproject is absent."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text('{"name":"ui-bastion"}', encoding="utf-8")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    content = (repo / ".zenzic.toml").read_text(encoding="utf-8")
    assert '# name = "ui-bastion"' in content


def test_init_pyproject_flag_appends_tool_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--pyproject appends [tool.zenzic] to an existing pyproject.toml."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "myapp"\n', encoding="utf-8")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init", "--pyproject"])
    assert result.exit_code == 0

    content = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.zenzic]" in content
    assert 'name = "myapp"' in content  # original content preserved

    assert (repo / ".zenzic.local.toml").is_file()
    assert ".zenzic.local.toml" in (repo / ".gitignore").read_text(encoding="utf-8")


def test_init_pyproject_section_comment_has_no_phantom_docs_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[tool.zenzic] header comment must not bake in a phantom /docs/-prefixed URL.

    Regression for: PYPROJECT_TOML_SECTION_TEMPLATE's "Full reference:"
    comment pointed at https://zenzic.dev/docs/reference/configuration/ — the
    real page is docs/reference/configuration-reference.md, served at
    /reference/configuration-reference/ (no /docs/ prefix, and the slug was
    also wrong), same defect class already fixed in README.md this session.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "myapp"\n', encoding="utf-8")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init", "--pyproject"])
    assert result.exit_code == 0, result.output

    content = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert "zenzic.dev/docs/" not in content, (
        f"Phantom /docs/-prefixed URL in pyproject.toml comment:\n{content}"
    )
    assert "zenzic.dev/reference/configuration-reference" in content


def test_init_preserves_existing_local_file_and_backfills_gitignore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Init aborts atomically when .zenzic.local.toml already exists."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / ".gitignore").write_text("# baseline\n", encoding="utf-8")
    original_local = "[governance]\nsuppression_cap = 123\n"
    (repo / ".zenzic.local.toml").write_text(original_local, encoding="utf-8")
    monkeypatch.chdir(repo)

    gitignore_before = (repo / ".gitignore").read_text(encoding="utf-8")
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 1
    assert "Configuration already exists" in result.stdout

    assert (repo / ".zenzic.local.toml").read_text(encoding="utf-8") == original_local
    assert (repo / ".gitignore").read_text(encoding="utf-8") == gitignore_before
    assert not (repo / ".zenzic.toml").exists()


def test_init_pyproject_with_mkdocs_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--pyproject detects mkdocs and writes [tool.zenzic.build_context]."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    (repo / "mkdocs.yml").write_text("site_name: x\n", encoding="utf-8")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init", "--pyproject"])
    assert result.exit_code == 0

    content = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.zenzic.build_context]" in content
    assert 'engine         = "mkdocs"' in content


def test_init_pyproject_warns_if_section_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse to overwrite existing [tool.zenzic] without --force."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "x"\n\n[tool.zenzic]\nfail_under = 80\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init", "--pyproject"])
    assert result.exit_code == 1
    assert "Configuration already exists" in result.stdout
    normalized = " ".join(result.stdout.split())
    assert "Manual editing is required" in normalized


def test_init_pyproject_force_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--pyproject --force is rejected in hardened init mode."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "x"\n\n[tool.zenzic]\nfail_under = 80\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init", "--pyproject", "--force"])
    assert result.exit_code == 1
    assert "--force is not supported" in result.stdout


def test_init_pyproject_no_file_creates_minimal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--pyproject without a pyproject.toml creates a minimal file and appends [tool.zenzic]."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init", "--pyproject"])
    assert result.exit_code == 0

    pyproject = repo / "pyproject.toml"
    assert pyproject.is_file()
    content = pyproject.read_text(encoding="utf-8")
    assert "[tool.zenzic]" in content
    assert "[tool.zenzic.governance]" in content
    assert "suppression_cap = 30" in content


def test_init_interactive_prompt_chooses_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When pyproject.toml exists and user answers 'y', config goes into pyproject."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init"], input="y\n")
    assert result.exit_code == 0

    content = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.zenzic]" in content
    assert not (repo / ".zenzic.toml").is_file()


def test_init_interactive_prompt_chooses_standalone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When pyproject.toml exists and user answers 'n', creates .zenzic.toml."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init"], input="n\n")
    assert result.exit_code == 0
    assert (repo / ".zenzic.toml").is_file()

    # pyproject.toml must NOT have [tool.zenzic]
    content = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.zenzic]" not in content


# ---------------------------------------------------------------------------
# diff — FATAL / HALT semantic parity
# ---------------------------------------------------------------------------


def _diff_baseline_json(tmp_path: Path, score: int = 100) -> Path:
    """Write a minimal baseline JSON snapshot for --base tests."""
    payload = {
        "score": score,
        "threshold": 0,
        "categories": [
            {
                "name": "structural",
                "weight": 0.30,
                "issues": 0,
                "category_score": 1.0,
                "contribution": 0.30,
            },
            {
                "name": "navigation",
                "weight": 0.25,
                "issues": 0,
                "category_score": 1.0,
                "contribution": 0.25,
            },
            {
                "name": "content",
                "weight": 0.20,
                "issues": 0,
                "category_score": 1.0,
                "contribution": 0.20,
            },
            {
                "name": "brand",
                "weight": 0.25,
                "issues": 0,
                "category_score": 1.0,
                "contribution": 0.25,
            },
        ],
    }
    p = tmp_path / "baseline.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _fatal_report() -> object:
    """ScoreReport simulating a Z201 credential leak (FATAL / security_override)."""
    from zenzic.core.scorer import CategoryScore, ScoreReport

    cats = [
        CategoryScore(
            name="structural", weight=0.30, issues=0, category_score=0.0, contribution=0.0
        ),
        CategoryScore(
            name="navigation", weight=0.25, issues=0, category_score=0.0, contribution=0.0
        ),
        CategoryScore(name="content", weight=0.20, issues=0, category_score=0.0, contribution=0.0),
        CategoryScore(name="brand", weight=0.25, issues=0, category_score=0.0, contribution=0.0),
    ]
    return ScoreReport(
        score=0,
        security_override=True,
        security_findings=1,
        findings_counts={"Z201": 1},
        categories=cats,
    )


def _z0xx_only_report() -> object:
    """ScoreReport with a synthetic Z0xx-prefixed key and no real Z2xx/security finding.

    Z0xx codes (config abort, e.g. Z001) can never actually reach
    findings_counts in practice — ZenzicConfig.load() raises ConfigurationError
    and exits 1 before _run_all_checks() is ever called. This fixture forces
    the scenario synthetically to lock the *intended* contract: diff's fatal
    detection considers Z2xx only, not a stale "Z0xx or Z2xx" prefix check.
    """
    from zenzic.core.scorer import CategoryScore, ScoreReport

    cats = [
        CategoryScore(
            name="structural", weight=0.30, issues=1, category_score=0.9, contribution=0.27
        ),
        CategoryScore(
            name="navigation", weight=0.25, issues=0, category_score=1.0, contribution=0.25
        ),
        CategoryScore(name="content", weight=0.20, issues=0, category_score=1.0, contribution=0.20),
        CategoryScore(name="brand", weight=0.25, issues=0, category_score=1.0, contribution=0.25),
    ]
    return ScoreReport(score=100, findings_counts={"Z001": 1}, categories=cats)


@patch("zenzic.cli._shared._build_exclusion_manager")
@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._standalone.find_repo_root", return_value=_ROOT)
def test_diff_z0xx_only_does_not_trigger_fatal(
    _root, _cfg, mock_run, _excl, tmp_path: Path
) -> None:
    """A synthetic Z0xx-only findings_counts entry must NOT trigger FATAL/Exit 2.

    Locks diff's fatal detection to Z2xx (security) only, guarding against the
    removed "Z0xx or Z2xx" prefix check being silently reintroduced.
    """
    mock_run.return_value = _z0xx_only_report()
    baseline = _diff_baseline_json(tmp_path, score=100)
    result = runner.invoke(app, ["diff", "--format", "json", "--base", str(baseline)])
    assert result.exit_code != 2, result.output
    data = json.loads(result.stdout)
    assert data["fatal_override"] is False
    assert data["fatal_codes"] == []


def _halt_report() -> object:
    """ScoreReport simulating a Z504 Quality Regression gate (HALT, warning+0.0 penalty)."""
    from zenzic.core.scorer import CategoryScore, ScoreReport

    cats = [
        CategoryScore(
            name="structural", weight=0.30, issues=0, category_score=1.0, contribution=0.30
        ),
        CategoryScore(
            name="navigation", weight=0.25, issues=0, category_score=1.0, contribution=0.25
        ),
        CategoryScore(name="content", weight=0.20, issues=0, category_score=1.0, contribution=0.20),
        CategoryScore(name="brand", weight=0.25, issues=0, category_score=1.0, contribution=0.25),
    ]
    return ScoreReport(score=100, findings_counts={"Z504": 1}, categories=cats)


@patch("zenzic.cli._shared._build_exclusion_manager")
@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._standalone.find_repo_root", return_value=_ROOT)
def test_diff_fatal_z201_exits_2(_root, _cfg, mock_run, _excl, tmp_path: Path) -> None:
    """zenzic diff exits 2 (non-suppressible) when current state has Z201."""
    mock_run.return_value = _fatal_report()
    baseline = _diff_baseline_json(tmp_path, score=100)
    result = runner.invoke(app, ["diff", "--base", str(baseline)])
    assert result.exit_code == 2


@patch("zenzic.cli._shared._build_exclusion_manager")
@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._standalone.find_repo_root", return_value=_ROOT)
def test_diff_fatal_output_surfaces_fatal_banner(
    _root, _cfg, mock_run, _excl, tmp_path: Path
) -> None:
    """zenzic diff text output shows FATAL OVERRIDE banner and Z201 code."""
    mock_run.return_value = _fatal_report()
    baseline = _diff_baseline_json(tmp_path, score=100)
    result = runner.invoke(app, ["diff", "--base", str(baseline)])
    assert "FATAL" in result.stdout
    assert "Z201" in result.stdout
    # Standard numeric delta must NOT be mistaken for the whole story
    assert "REGRESSION" not in result.stdout


@patch("zenzic.cli._shared._build_exclusion_manager")
@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._standalone.find_repo_root", return_value=_ROOT)
def test_diff_fatal_json_fields(_root, _cfg, mock_run, _excl, tmp_path: Path) -> None:
    """zenzic diff --format json includes fatal_override, fatal_codes, halt, halt_codes."""
    mock_run.return_value = _fatal_report()
    baseline = _diff_baseline_json(tmp_path, score=100)
    result = runner.invoke(app, ["diff", "--format", "json", "--base", str(baseline)])
    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["fatal_override"] is True
    assert "Z201" in data["fatal_codes"]
    assert data["halt"] is False
    assert data["halt_codes"] == []


@patch("zenzic.cli._shared._build_exclusion_manager")
@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._standalone.find_repo_root", return_value=_ROOT)
def test_diff_halt_z504_exits_1(_root, _cfg, mock_run, _excl, tmp_path: Path) -> None:
    """zenzic diff exits 1 and surfaces HALT when current state has Z504 (pipeline gate)."""
    mock_run.return_value = _halt_report()
    baseline = _diff_baseline_json(tmp_path, score=100)
    result = runner.invoke(app, ["diff", "--base", str(baseline)])
    assert result.exit_code == 1
    assert "HALT" in result.stdout
    assert "Z504" in result.stdout


@patch("zenzic.cli._shared._build_exclusion_manager")
@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._standalone.find_repo_root", return_value=_ROOT)
def test_diff_standard_regression_no_fatal_halt(
    _root, _cfg, mock_run, _excl, tmp_path: Path
) -> None:
    """A plain score drop (Z101, no Z2xx/Z0xx/halt gate) must not trigger FATAL or HALT."""
    from zenzic.core.scorer import CategoryScore, ScoreReport

    cats = [
        CategoryScore(
            name="structural", weight=0.30, issues=2, category_score=0.467, contribution=0.14
        ),
        CategoryScore(
            name="navigation", weight=0.25, issues=0, category_score=1.0, contribution=0.25
        ),
        CategoryScore(name="content", weight=0.20, issues=0, category_score=1.0, contribution=0.20),
        CategoryScore(name="brand", weight=0.25, issues=0, category_score=1.0, contribution=0.25),
    ]
    mock_run.return_value = ScoreReport(score=84, findings_counts={"Z101": 2}, categories=cats)
    baseline = _diff_baseline_json(tmp_path, score=100)
    result = runner.invoke(app, ["diff", "--base", str(baseline)])
    assert result.exit_code == 1
    assert "FATAL" not in result.stdout
    assert "HALT" not in result.stdout
    assert "REGRESSION" in result.stdout


def test_init_standalone_no_engine_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without mkdocs.yml or zensical.toml, standalone feedback is shown."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    assert "standalone" in result.stdout.lower() or "engine-agnostic" in result.stdout.lower()


# ---------------------------------------------------------------------------
# init — ZRT-005 Bootstrap Paradox (Genesis Fallback)
# ---------------------------------------------------------------------------


def test_init_in_fresh_directory_no_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ZRT-005: zenzic init must succeed in a brand-new directory with no .git."""
    fresh = tmp_path / "brand_new_project"
    fresh.mkdir()
    monkeypatch.chdir(fresh)

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.stdout
    assert (fresh / ".zenzic.toml").is_file()


def test_init_nomad_writes_to_target_not_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CEO-060 'The Nomad': zenzic init <path> creates .zenzic.toml at target, not CWD."""
    target = tmp_path / "new-docs"
    target.mkdir()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    result = runner.invoke(app, ["init", str(target)])
    assert result.exit_code == 0, result.stdout
    assert (target / ".zenzic.toml").is_file(), ".zenzic.toml must be at target"
    assert not (workspace / ".zenzic.toml").is_file(), ".zenzic.toml must NOT appear in CWD"


def test_init_nomad_creates_target_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CEO-060: zenzic init <nonexistent-path> must create the directory and write .zenzic.toml."""
    target = tmp_path / "does" / "not" / "exist"
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init", str(target)])
    assert result.exit_code == 0, result.stdout
    assert (target / ".zenzic.toml").is_file(), ".zenzic.toml must be created at nested target"


# ---------------------------------------------------------------------------
# init — --engine flag
# ---------------------------------------------------------------------------


def test_init_engine_flag_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--engine ENGINE writes that engine into .zenzic.toml regardless of auto-detection."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    # mkdocs.yml present — auto-detect would pick "mkdocs" — flag must win
    (repo / "mkdocs.yml").write_text("site_name: test\n", encoding="utf-8")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init", "--engine", "zensical"])
    assert result.exit_code == 0

    content = (repo / ".zenzic.toml").read_text(encoding="utf-8")
    assert 'engine         = "zensical"' in content
    assert "(manually specified via --engine)" in result.stdout


def test_init_engine_flag_invalid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--engine <unknown> exits with a clear error listing valid values."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init", "--engine", "hugo"])
    assert result.exit_code == 1
    assert "hugo" in result.stdout
    assert "mkdocs" in result.stdout  # valid engine listed in error


def test_init_pyproject_engine_flag_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--pyproject --engine ENGINE writes that engine into [tool.zenzic.build_context]."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init", "--pyproject", "--engine", "zensical"])
    assert result.exit_code == 0

    content = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert 'engine         = "zensical"' in content
    assert "(manually specified via --engine)" in result.stdout


def test_init_pyproject_template_verbose(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """pyproject.toml template includes didactic comments matching .zenzic.toml quality."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "myapp"\n', encoding="utf-8")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["init", "--pyproject"])
    assert result.exit_code == 0

    content = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert "ORTHOGONAL CONSTRAINTS" in content
    assert "suppression_cap" in content
    assert "CI/CD" in content
    assert "[tool.zenzic.governance.per_file_ignores]" in content
    assert "[tool.zenzic.governance.directory_policies]" in content
    assert "excluded_dirs" in content


# ---------------------------------------------------------------------------
# Signal-to-Noise: --show-info / reporter show_info filter
# ---------------------------------------------------------------------------


class TestShowInfoFilter:
    """Verify that info-severity findings are suppressed by default and shown with --show-info."""

    @staticmethod
    def _make_reporter(buf):
        from rich.console import Console

        from zenzic.core.reporter import ZenzicReporter

        con = Console(file=buf, highlight=False, markup=True)
        return ZenzicReporter(con, Path("/fake/docs"), docs_dir="docs")

    @staticmethod
    def _info_finding():
        from zenzic.core.reporter import Finding

        return Finding(
            rel_path="guide/nav.md",
            line_no=5,
            code="CIRCULAR_LINK",
            severity="info",
            message="guide/nav.md:5: 'index.md' is part of a circular link cycle",
            source_line="[Home](index.md)",
        )

    def test_info_finding_suppressed_by_default(self) -> None:
        """With show_info=False (default), info findings must not appear in output."""
        import io

        buf = io.StringIO()
        reporter = self._make_reporter(buf)
        errors, warnings = reporter.render(
            [self._info_finding()],
            version="0.5.0a4",
            elapsed=0.0,
            show_info=False,
        )
        out = buf.getvalue()
        assert "CIRCULAR_LINK" not in out
        assert "suppressed" in out
        assert errors == 0
        assert warnings == 0

    def test_info_finding_shown_with_show_info_true(self) -> None:
        """With show_info=True, info findings must appear in output and no suppression note."""
        import io

        buf = io.StringIO()
        reporter = self._make_reporter(buf)
        errors, warnings = reporter.render(
            [self._info_finding()],
            version="0.5.0a4",
            elapsed=0.0,
            show_info=True,
        )
        out = buf.getvalue()
        assert "CIRCULAR_LINK" in out
        assert "suppressed" not in out
        assert errors == 0
        assert warnings == 0

    @patch("zenzic.cli._shared._count_docs_assets", return_value=(5, 0))
    @patch("zenzic.cli._check.find_repo_root", return_value=_ROOT)
    @patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
    @patch("zenzic.cli._check.validate_links_structured", return_value=[])
    @patch("zenzic.cli._check.find_orphans", return_value=[])
    @patch("zenzic.cli._check.validate_snippets", return_value=[])
    @patch("zenzic.cli._check.find_unused_assets", return_value=[])
    @patch("zenzic.cli._check.check_nav_contract", return_value=[])
    @patch("zenzic.cli._check.scan_docs_references", return_value=([], []))
    def test_check_all_show_info_flag_accepted(
        self, _refs, _nav, _assets, _snip, _orphans, _links, _cfg, _root, _count
    ) -> None:
        """--show-info flag must be accepted by check all without crashing."""
        result = runner.invoke(app, ["check", "all", "--show-info"])
        assert result.exit_code == 0, result.stdout


# ---------------------------------------------------------------------------
# inspect capabilities — D083 Iron Gate
# ---------------------------------------------------------------------------


def test_inspect_capabilities_shows_bypass_table() -> None:
    """inspect capabilities must render Section C with engine-specific bypass schemes."""
    result = runner.invoke(app, ["inspect", "capabilities"])
    assert result.exit_code == 0
    assert "Engine-specific Link Bypasses" in result.stdout
    assert "zensical" in result.stdout
    assert "R21" in result.stdout


# ---------------------------------------------------------------------------
# score — D083 Iron Gate
# ---------------------------------------------------------------------------


@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone.ZenzicConfig.load")
@patch("zenzic.cli._standalone.find_repo_root")
def test_score_json_baseline_status_absent_when_no_snapshot(
    mock_root: object, mock_cfg: object, mock_run: object, tmp_path: Path
) -> None:
    """score --json reports baseline_status='absent' when no .zenzic-score.json exists."""
    from zenzic.core.scorer import CategoryScore, ScoreReport

    mock_root.return_value = tmp_path  # type: ignore[attr-defined]
    mock_cfg.return_value = (_CFG, False)  # type: ignore[attr-defined]
    mock_run.return_value = ScoreReport(  # type: ignore[attr-defined]
        score=100,
        categories=[
            CategoryScore("structural", 0.30, 0, 1.0, 0.30),
            CategoryScore("navigation", 0.25, 0, 1.0, 0.25),
            CategoryScore("content", 0.20, 0, 1.0, 0.20),
            CategoryScore("brand", 0.25, 0, 1.0, 0.25),
        ],
    )
    result = runner.invoke(app, ["score", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["baseline_status"] == "absent"
    assert data["baseline_age_days"] is None


@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone.ZenzicConfig.load")
@patch("zenzic.cli._standalone.find_repo_root")
def test_score_json_baseline_status_fresh_within_threshold(
    mock_root: object, mock_cfg: object, mock_run: object, tmp_path: Path
) -> None:
    """score --json reports baseline_status='fresh' for a recently saved snapshot."""
    from zenzic.core.scorer import CategoryScore, ScoreReport

    (tmp_path / ".zenzic-score.json").write_text("{}", encoding="utf-8")
    mock_root.return_value = tmp_path  # type: ignore[attr-defined]
    mock_cfg.return_value = (_CFG, False)  # type: ignore[attr-defined]
    mock_run.return_value = ScoreReport(  # type: ignore[attr-defined]
        score=100,
        categories=[
            CategoryScore("structural", 0.30, 0, 1.0, 0.30),
            CategoryScore("navigation", 0.25, 0, 1.0, 0.25),
            CategoryScore("content", 0.20, 0, 1.0, 0.20),
            CategoryScore("brand", 0.25, 0, 1.0, 0.25),
        ],
    )
    result = runner.invoke(app, ["score", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["baseline_status"] == "fresh"
    assert data["baseline_age_days"] == 0


@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone.ZenzicConfig.load")
@patch("zenzic.cli._standalone.find_repo_root")
def test_score_json_baseline_status_stale_beyond_threshold(
    mock_root: object, mock_cfg: object, mock_run: object, tmp_path: Path
) -> None:
    """score --json reports baseline_status='stale' when the snapshot exceeds the threshold."""
    from zenzic.core.scorer import DEFAULT_BASELINE_STALE_DAYS, CategoryScore, ScoreReport

    snapshot = tmp_path / ".zenzic-score.json"
    snapshot.write_text("{}", encoding="utf-8")
    old_time = time.time() - (DEFAULT_BASELINE_STALE_DAYS + 1) * 86400
    os.utime(snapshot, (old_time, old_time))

    mock_root.return_value = tmp_path  # type: ignore[attr-defined]
    mock_cfg.return_value = (_CFG, False)  # type: ignore[attr-defined]
    mock_run.return_value = ScoreReport(  # type: ignore[attr-defined]
        score=100,
        categories=[
            CategoryScore("structural", 0.30, 0, 1.0, 0.30),
            CategoryScore("navigation", 0.25, 0, 1.0, 0.25),
            CategoryScore("content", 0.20, 0, 1.0, 0.20),
            CategoryScore("brand", 0.25, 0, 1.0, 0.25),
        ],
    )
    result = runner.invoke(app, ["score", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["baseline_status"] == "stale"
    assert data["baseline_age_days"] >= DEFAULT_BASELINE_STALE_DAYS + 1


@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone.ZenzicConfig.load")
@patch("zenzic.cli._standalone.find_repo_root")
def test_score_json_baseline_stale_days_config_override(
    mock_root: object, mock_cfg: object, mock_run: object, tmp_path: Path
) -> None:
    """A .zenzic.toml baseline_stale_days override changes the fresh/stale boundary."""
    from zenzic.core.scorer import CategoryScore, ScoreReport
    from zenzic.models.config import ZenzicConfig

    snapshot = tmp_path / ".zenzic-score.json"
    snapshot.write_text("{}", encoding="utf-8")
    old_time = time.time() - 2 * 86400  # 2 days old
    os.utime(snapshot, (old_time, old_time))

    custom_cfg = ZenzicConfig(baseline_stale_days=1)
    mock_root.return_value = tmp_path  # type: ignore[attr-defined]
    mock_cfg.return_value = (custom_cfg, True)  # type: ignore[attr-defined]
    mock_run.return_value = ScoreReport(  # type: ignore[attr-defined]
        score=100,
        categories=[
            CategoryScore("structural", 0.30, 0, 1.0, 0.30),
            CategoryScore("navigation", 0.25, 0, 1.0, 0.25),
            CategoryScore("content", 0.20, 0, 1.0, 0.20),
            CategoryScore("brand", 0.25, 0, 1.0, 0.25),
        ],
    )
    result = runner.invoke(app, ["score", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    # 2 days old, threshold=1 day → stale (would be "fresh" under the default 7-day threshold)
    assert data["baseline_status"] == "stale"


@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone.ZenzicConfig.load")
@patch("zenzic.cli._standalone.find_repo_root")
def test_score_json_trend_none_when_no_baseline(
    mock_root: object, mock_cfg: object, mock_run: object, tmp_path: Path
) -> None:
    """score --json reports score_trend=None when no snapshot exists to compare against."""
    from zenzic.core.scorer import CategoryScore, ScoreReport

    mock_root.return_value = tmp_path  # type: ignore[attr-defined]
    mock_cfg.return_value = (_CFG, False)  # type: ignore[attr-defined]
    mock_run.return_value = ScoreReport(  # type: ignore[attr-defined]
        score=91,
        categories=[
            CategoryScore("structural", 0.30, 0, 1.0, 0.30),
            CategoryScore("navigation", 0.25, 0, 1.0, 0.25),
            CategoryScore("content", 0.20, 0, 1.0, 0.20),
            CategoryScore("brand", 0.25, 0, 1.0, 0.25),
        ],
    )
    result = runner.invoke(app, ["score", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["score_trend"] is None


@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone.ZenzicConfig.load")
@patch("zenzic.cli._standalone.find_repo_root")
def test_score_json_trend_computed_from_saved_snapshot(
    mock_root: object, mock_cfg: object, mock_run: object, tmp_path: Path
) -> None:
    """score --json's score_trend reflects the delta against the saved snapshot."""
    from zenzic.core.scorer import CategoryScore, ScoreReport

    snapshot = tmp_path / ".zenzic-score.json"
    snapshot.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "score": 80,
                "threshold": 0,
                "categories": [
                    {
                        "name": "structural",
                        "weight": 0.30,
                        "issues": 2,
                        "category_score": 0.5,
                        "contribution": 0.15,
                        "raw_penalty": 15.0,
                        "is_capped": False,
                    }
                ],
                "suppression_count": 0,
                "suppression_cap": 30,
                "suppression_debt_pts": 0,
                "debt_status": "CLEAN",
            }
        ),
        encoding="utf-8",
    )
    mock_root.return_value = tmp_path  # type: ignore[attr-defined]
    mock_cfg.return_value = (_CFG, False)  # type: ignore[attr-defined]
    mock_run.return_value = ScoreReport(  # type: ignore[attr-defined]
        score=91,
        categories=[
            CategoryScore("structural", 0.30, 0, 1.0, 0.30),
            CategoryScore("navigation", 0.25, 0, 1.0, 0.25),
            CategoryScore("content", 0.20, 0, 1.0, 0.20),
            CategoryScore("brand", 0.25, 0, 1.0, 0.25),
        ],
    )
    result = runner.invoke(app, ["score", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["score_trend"] == {
        "baseline_score": 80,
        "current_score": 91,
        "delta": 11,
    }


@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone.ZenzicConfig.load")
@patch("zenzic.cli._standalone.find_repo_root")
def test_score_json_trend_none_when_snapshot_incompatible(
    mock_root: object, mock_cfg: object, mock_run: object, tmp_path: Path
) -> None:
    """score --json degrades gracefully (score_trend=None) for a legacy-schema snapshot."""
    from zenzic.core.scorer import CategoryScore, ScoreReport

    snapshot = tmp_path / ".zenzic-score.json"
    snapshot.write_text(json.dumps({"schema_version": 1, "score": 80}), encoding="utf-8")
    mock_root.return_value = tmp_path  # type: ignore[attr-defined]
    mock_cfg.return_value = (_CFG, False)  # type: ignore[attr-defined]
    mock_run.return_value = ScoreReport(  # type: ignore[attr-defined]
        score=91,
        categories=[
            CategoryScore("structural", 0.30, 0, 1.0, 0.30),
            CategoryScore("navigation", 0.25, 0, 1.0, 0.25),
            CategoryScore("content", 0.20, 0, 1.0, 0.20),
            CategoryScore("brand", 0.25, 0, 1.0, 0.25),
        ],
    )
    result = runner.invoke(app, ["score", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["score_trend"] is None


@patch("zenzic.cli._standalone.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._standalone.ZenzicConfig.load", return_value=(_CFG, False))
@patch("zenzic.cli._standalone._run_all_checks")
def test_score_perfect_shows_audit_complete(_run: object, _cfg: object, _root: object) -> None:
    """score at 100/100 must display the celebratory completion panel."""
    from zenzic.core.scorer import CategoryScore, ScoreReport

    _run.return_value = ScoreReport(  # type: ignore[attr-defined]
        score=100,
        categories=[
            CategoryScore("structural", 0.35, 0, 1.0, 0.35),
            CategoryScore("navigation", 0.20, 0, 1.0, 0.20),
            CategoryScore("content", 0.20, 0, 1.0, 0.20),
            CategoryScore("brand", 0.15, 0, 1.0, 0.15),
        ],
    )
    result = runner.invoke(app, ["score"])
    assert result.exit_code == 0
    assert "100/100" in result.stdout
    assert "Every check passed" in result.stdout


@patch("zenzic.cli._standalone.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._standalone.ZenzicConfig.load", return_value=(_CFG, False))
@patch("zenzic.cli._standalone._run_all_checks")
def test_score_low_uses_error_style(_run: object, _cfg: object, _root: object) -> None:
    """score below 50 must use red error styling and must NOT show the completion panel."""
    from zenzic.core.scorer import CategoryScore, ScoreReport

    _run.return_value = ScoreReport(  # type: ignore[attr-defined]
        score=30,
        categories=[
            CategoryScore("structural", 0.35, 5, 0.0, 0.0),
            CategoryScore("navigation", 0.20, 3, 0.40, 0.08),
            CategoryScore("content", 0.20, 0, 1.0, 0.20),
            CategoryScore("brand", 0.15, 1, 0.80, 0.12),
        ],
    )
    result = runner.invoke(app, ["score"])
    assert result.exit_code == 0
    assert "30/100" in result.stdout
    assert "Every check passed" not in result.stdout


@patch("zenzic.cli._standalone.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._standalone.ZenzicConfig.load", return_value=(_CFG, False))
@patch("zenzic.cli._standalone._run_all_checks")
def test_score_no_header_suppresses_banner(_run: object, _cfg: object, _root: object) -> None:
    """score --no-header must omit the PythonWoods banner panel from output."""
    from zenzic.core.scorer import CategoryScore, ScoreReport

    _run.return_value = ScoreReport(  # type: ignore[attr-defined]
        score=100,
        categories=[
            CategoryScore("structural", 0.35, 0, 1.0, 0.35),
            CategoryScore("navigation", 0.20, 0, 1.0, 0.20),
            CategoryScore("content", 0.20, 0, 1.0, 0.20),
            CategoryScore("brand", 0.15, 0, 1.0, 0.15),
        ],
    )
    result = runner.invoke(app, ["score", "--no-header"])
    assert result.exit_code == 0
    assert "PythonWoods" not in result.stdout
    assert "100/100" in result.stdout


@patch("zenzic.cli._standalone.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._standalone.ZenzicConfig.load", return_value=(_CFG, False))
@patch("zenzic.cli._standalone._run_all_checks")
def test_score_breakdown(_run: object, _cfg: object, _root: object) -> None:
    """score --breakdown must print category explosion and mathematical transparency."""
    from zenzic.core.scorer import CategoryScore, ScoreReport

    _run.return_value = ScoreReport(  # type: ignore[attr-defined]
        score=85,
        categories=[
            CategoryScore("structural", 0.30, 1, 0.80, 0.24, raw_penalty=8.0, is_capped=False),
            CategoryScore("navigation", 0.25, 1, 0.90, 0.225, raw_penalty=4.0, is_capped=False),
            CategoryScore("content", 0.20, 0, 1.0, 0.20, raw_penalty=0.0, is_capped=False),
            CategoryScore("brand", 0.25, 0, 1.0, 0.25, raw_penalty=0.0, is_capped=False),
        ],
        findings_counts={"Z101": 1, "Z402": 1, "Z106": 2},
        suppression_count=3,
        suppression_cap=30,
        debt_status="MANAGED",
        suppression_debt_pts=3,
    )
    result = runner.invoke(app, ["score", "--breakdown"])
    assert result.exit_code == 0
    assert "DETAILED CATEGORY BREAKDOWN" in result.stdout
    assert "STRUCTURAL CATEGORY" in result.stdout
    assert "Z101 (LINK_BROKEN)" in result.stdout
    assert "Z106 (CIRCULAR_LINK)" in result.stdout
    assert "DQS MATHEMATICAL TRANSPARENCY" in result.stdout
    assert "Base Score:" in result.stdout
    assert "Total Category Penalties:" in result.stdout
    assert "Technical Debt Penalty:" in result.stdout

    single_char_separator_lines = [line for line in result.stdout.splitlines() if line == "━"]
    assert not single_char_separator_lines, (
        "Expected compact ━ separator lines (one line, many characters), not one line per "
        f"character; found {len(single_char_separator_lines)} single-character separator lines "
        "in the output — this is the fragmented-separator regression."
    )
    full_width_separator_lines = [
        line for line in result.stdout.splitlines() if line.count("━") >= 40
    ]
    assert len(full_width_separator_lines) >= 2, (
        "Expected at least 2 full-width ━ separator lines (before the category breakdown and "
        f"before the mathematical transparency section); found {full_width_separator_lines!r}"
    )


@patch("zenzic.cli._standalone.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._standalone.ZenzicConfig.load", return_value=(_CFG, False))
@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone._check_stamp_file", return_value=True)
def test_score_check_stamp_passes_when_current(
    _chk: object, _run: object, _cfg: object, _root: object
) -> None:
    """score --check-stamp must exit 0 and report all badges current when fresh."""
    from zenzic.core.scorer import CategoryScore, ScoreReport

    _run.return_value = ScoreReport(  # type: ignore[attr-defined]
        score=100,
        categories=[
            CategoryScore("structural", 0.35, 0, 1.0, 0.35),
            CategoryScore("navigation", 0.20, 0, 1.0, 0.20),
            CategoryScore("content", 0.20, 0, 1.0, 0.20),
            CategoryScore("brand", 0.15, 0, 1.0, 0.15),
        ],
    )
    result = runner.invoke(app, ["score", "--check-stamp", "--no-header"])
    assert result.exit_code == 0
    assert "Quality Breakdown" not in result.stdout
    assert "All badges are current" in result.stdout


@patch("zenzic.cli._standalone.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._standalone.ZenzicConfig.load", return_value=(_CFG, False))
@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone._check_stamp_file", return_value=False)
def test_score_check_stamp_fails_when_stale(
    _chk: object, _run: object, _cfg: object, _root: object
) -> None:
    """score --check-stamp must exit 1 and name the stale file when badge is outdated."""
    from zenzic.core.scorer import CategoryScore, ScoreReport

    _run.return_value = ScoreReport(  # type: ignore[attr-defined]
        score=95,
        categories=[
            CategoryScore("structural", 0.35, 0, 1.0, 0.35),
            CategoryScore("navigation", 0.20, 0, 1.0, 0.20),
            CategoryScore("content", 0.20, 0, 1.0, 0.20),
            CategoryScore("brand", 0.15, 0, 1.0, 0.15),
        ],
    )
    result = runner.invoke(app, ["score", "--check-stamp", "--no-header"])
    assert result.exit_code == 1
    assert "Quality Breakdown" not in result.stdout
    assert "[FAILED] Badge (score) in" in result.stdout
    assert "[FAILED] Badge (audit) in" in result.stdout


@patch("zenzic.cli._standalone.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._standalone.ZenzicConfig.load", return_value=(_CFG, False))
@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone._check_stamp_file", side_effect=[False, True])
def test_score_check_stamp_fails_when_score_badge_stale_only(
    _chk: object, _run: object, _cfg: object, _root: object
) -> None:
    """score --check-stamp reports score marker drift independently from audit marker."""
    from zenzic.core.scorer import CategoryScore, ScoreReport

    _run.return_value = ScoreReport(  # type: ignore[attr-defined]
        score=100,
        categories=[
            CategoryScore("structural", 0.35, 0, 1.0, 0.35),
            CategoryScore("navigation", 0.20, 0, 1.0, 0.20),
            CategoryScore("content", 0.20, 0, 1.0, 0.20),
            CategoryScore("brand", 0.15, 0, 1.0, 0.15),
        ],
    )
    result = runner.invoke(app, ["score", "--check-stamp", "--no-header"])
    assert result.exit_code == 1
    assert "Badge (score)" in result.stdout
    assert "Badge (audit)" not in result.stdout


@patch("zenzic.cli._standalone.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._standalone.ZenzicConfig.load", return_value=(_CFG, False))
@patch("zenzic.cli._standalone._run_all_checks")
@patch("zenzic.cli._standalone._check_stamp_file", side_effect=[True, False])
def test_score_check_stamp_fails_when_audit_badge_stale_only(
    _chk: object, _run: object, _cfg: object, _root: object
) -> None:
    """score --check-stamp reports audit marker drift independently from score marker."""
    from zenzic.core.scorer import CategoryScore, ScoreReport

    _run.return_value = ScoreReport(  # type: ignore[attr-defined]
        score=100,
        categories=[
            CategoryScore("structural", 0.35, 0, 1.0, 0.35),
            CategoryScore("navigation", 0.20, 0, 1.0, 0.20),
            CategoryScore("content", 0.20, 0, 1.0, 0.20),
            CategoryScore("brand", 0.15, 0, 1.0, 0.15),
        ],
    )
    result = runner.invoke(app, ["score", "--check-stamp", "--no-header"])
    assert result.exit_code == 1
    assert "Badge (audit)" in result.stdout
    assert "Badge (score)" not in result.stdout


@patch("zenzic.cli._standalone.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._standalone.ZenzicConfig.load", return_value=(_CFG, False))
def test_score_check_stamp_and_stamp_mutually_exclusive(_cfg: object, _root: object) -> None:
    """score --stamp --check-stamp must exit 1 with a clear mutual-exclusivity error."""
    result = runner.invoke(app, ["score", "--stamp", "--check-stamp"])
    assert result.exit_code == 1
    assert "mutually exclusive" in result.output


# ---------------------------------------------------------------------------


@patch("zenzic.cli._command_setup.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, False))
@patch("zenzic.cli._check.validate_links_structured", return_value=[])
def test_check_links_short_format_alias(_links, _cfg, _root) -> None:
    """-f json must be accepted as alias for --format json in check links."""
    result = runner.invoke(app, ["check", "links", "-f", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "findings" in data or isinstance(data, list | dict)


@patch("zenzic.cli._command_setup.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, False))
@patch("zenzic.cli._check.find_orphans", return_value=[])
def test_check_orphans_short_format_alias(_orphans, _cfg, _root) -> None:
    """-f json must be accepted as alias for --format json in check orphans."""
    result = runner.invoke(app, ["check", "orphans", "-f", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "findings" in data or isinstance(data, list | dict)


@patch("zenzic.cli._check.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, False))
@patch("zenzic.cli._check.validate_links_structured", return_value=[])
@patch("zenzic.cli._check.find_orphans", return_value=[])
@patch("zenzic.cli._check.validate_snippets", return_value=[])
@patch("zenzic.cli._check.find_unused_assets", return_value=[])
@patch("zenzic.cli._check.check_nav_contract", return_value=[])
@patch("zenzic.cli._check.scan_docs_references", return_value=([], []))
def test_check_all_short_format_alias(
    _refs, _nav, _assets, _snip, _orphans, _links, _cfg, _root
) -> None:
    """-f json must be accepted as alias for --format json in check all."""
    result = runner.invoke(app, ["check", "all", "-f", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "findings" in data or isinstance(data, list | dict)


# ---------------------------------------------------------------------------
# GAP-02: init --plugin conflict validation
# ---------------------------------------------------------------------------


def test_init_local_flag_scaffolds_only_local_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--local must create only .zenzic.local.toml; .zenzic.toml must not be created."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--local"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".zenzic.local.toml").exists()
    assert "forbidden_patterns = []" in (tmp_path / ".zenzic.local.toml").read_text(
        encoding="utf-8"
    )
    assert not (tmp_path / ".zenzic.toml").exists()


def test_init_local_flag_gitignore_note_renders_real_newline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 'Zenzic Local Sandbox' panel must render a real line break, not '\\n'.

    Regression for: the gitignore-status lines appended in ``_scaffold_local_toml``
    (``_standalone.py``) were built with a literal ``"...\\\\n"`` (double-escaped)
    instead of a real ``"\\n"``, so the panel printed the two literal characters
    backslash-n instead of breaking to a new line. Covers the "additions made"
    branch (site 1: gitignore created/appended).
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    result = runner.invoke(app, ["init", "--local"])
    assert result.exit_code == 0, result.output
    assert "\\n" not in result.output, (
        f"Literal backslash-n leaked into panel output:\n{result.output}"
    )
    assert "Security Note" in result.output


def test_init_local_flag_gitignore_already_protects_note_renders_real_newline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Covers the "already protects" branch (site 2) for the same '\\n' bug."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".gitignore").write_text(".zenzic.local.toml\n.zenzic_cache/\n", encoding="utf-8")
    result = runner.invoke(app, ["init", "--local"])
    assert result.exit_code == 0, result.output
    assert "\\n" not in result.output, (
        f"Literal backslash-n leaked into panel output:\n{result.output}"
    )
    assert "already protects" in result.output


def test_init_local_flag_no_git_repo_note_renders_real_newline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Covers the "no Git repository detected" branch (site 3) for the same '\\n' bug."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--local"])
    assert result.exit_code == 0, result.output
    assert "\\n" not in result.output, (
        f"Literal backslash-n leaked into panel output:\n{result.output}"
    )
    assert "No Git repository detected" in result.output


def test_init_next_steps_ci_cd_link_has_no_phantom_docs_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """'Next steps' CI/CD link must not bake in a phantom /docs/-prefixed URL.

    Regression for: the link pointed at
    https://zenzic.dev/docs/how-to/configure-ci-cd — mkdocs serves
    docs/how-to/configure-ci-cd.md at /how-to/configure-ci-cd/ (docs_dir is
    stripped from the served path, same defect class already fixed in
    README.md this session), so the shipped link 404s.
    """
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    assert "zenzic.dev/docs/" not in result.output, (
        f"Phantom /docs/-prefixed URL in 'Next steps' output:\n{result.output}"
    )
    assert "zenzic.dev/how-to/configure-ci-cd" in result.output


def test_init_plugin_local_conflict_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--plugin combined with --local is a plain CLI-usage error: exit 1, not Exit 2

    (Exit 2 is reserved for security breaches — Tier-0 Exit Code Contract).
    """
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--plugin", "myrule", "--local"])
    assert result.exit_code == 1, result.output
    assert "--plugin" in result.output or "cannot be combined" in result.output.lower()


def test_init_plugin_pyproject_conflict_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--plugin combined with --pyproject is a plain CLI-usage error: exit 1, not Exit 2."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--plugin", "myrule", "--pyproject"])
    assert result.exit_code == 1, result.output
    assert "--plugin" in result.output or "cannot be combined" in result.output.lower()


def test_init_plugin_alone_does_not_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--plugin without conflicting flags must not raise a conflict (scaffold runs)."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--plugin", "myrule"])
    # Exit 0 = scaffold created. Any non-1 exit is fine here (no conflict raised).
    assert result.exit_code != 1, result.output


def test_init_flag_conflicts_use_the_same_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All of init's flag-conflict checks must agree on one exit code.

    Regression guard: --plugin+--local/--pyproject and --local+--pyproject
    previously diverged (Exit 2 vs Exit 1) for structurally identical
    "these flags cannot combine" errors, with no principled reason for the
    difference (V031_CODE_BACKLOG_BATCH1_EXECUTION_AND_PROACTIVE_ADVISORY_CODIFICATION).
    This test locks all three conflict pairs to the same exit code so a third
    site can't silently reintroduce the divergence.
    """
    monkeypatch.chdir(tmp_path)
    plugin_local = runner.invoke(app, ["init", "--plugin", "myrule", "--local"])
    plugin_pyproject = runner.invoke(app, ["init", "--plugin", "myrule", "--pyproject"])
    local_pyproject = runner.invoke(app, ["init", "--local", "--pyproject"])
    assert plugin_local.exit_code == plugin_pyproject.exit_code == local_pyproject.exit_code == 1


def test_check_all_config_flag_loads_explicit_override_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--config PATH must load that exact file instead of discovering .zenzic.toml.

    Proves real end-to-end threading (CLI option → ZenzicConfig.load(config_file=...))
    by pointing docs_dir at a directory only the override config names.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "wrong_docs").mkdir()
    (tmp_path / "wrong_docs" / "index.md").write_text("# Wrong\n")
    override_docs = tmp_path / "right_docs"
    override_docs.mkdir()
    (override_docs / "index.md").write_text("# Right\n")

    # A .zenzic.toml at repo_root pointing at the WRONG docs dir — must be ignored
    # entirely once --config names a different file.
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "wrong_docs"\n')

    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    override_config = configs_dir / "prod.toml"
    override_config.write_text('docs_dir = "right_docs"\n')

    result = runner.invoke(
        app, ["check", "all", "--config", str(override_config), "--format", "json", "--quiet"]
    )
    assert result.exit_code in (0, 1), result.output
    payload = json.loads(result.stdout)
    # The override config's docs_dir ("right_docs") was scanned — its page heading
    # ("Right") appears in the findings. "wrong_docs" (from .zenzic.toml, which the
    # override must take priority over) was never scanned at all.
    assert "Right" in json.dumps(payload)
    assert "Wrong" not in json.dumps(payload)


def test_check_all_config_flag_missing_file_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--config pointing at a nonexistent file must fail, not silently fall back to discovery."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["check", "all", "--config", str(tmp_path / "nope.toml")])
    assert result.exit_code != 0


def test_score_config_flag_loads_explicit_override_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """zenzic score --config PATH loads that exact file instead of discovering .zenzic.toml."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "wrong_docs").mkdir()
    (tmp_path / "wrong_docs" / "index.md").write_text("# Wrong\n")
    (tmp_path / "right_docs").mkdir()
    (tmp_path / "right_docs" / "index.md").write_text("# Right\n")
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "wrong_docs"\n')
    override_config = tmp_path / "prod.toml"
    override_config.write_text('docs_dir = "right_docs"\n')

    result = runner.invoke(
        app, ["score", "--config", str(override_config), "--format", "json", "--no-header"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    # Only "right_docs" (from the override config) was scored: 1 issue for the
    # short page. "wrong_docs" (from .zenzic.toml) must be entirely ignored.
    assert payload["categories"][2]["issues"] >= 1  # content category


def test_score_config_flag_missing_file_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """zenzic score --config pointing at a nonexistent file must fail cleanly."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["score", "--config", str(tmp_path / "nope.toml")])
    assert result.exit_code != 0
    assert "does not exist" in result.output or "ERROR" in result.output


def test_diff_config_flag_threaded_to_config_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """zenzic diff --config PATH loads that exact file (proven via a missing-file error)."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["diff", "--config", str(tmp_path / "nope.toml")])
    assert result.exit_code != 0
    assert "does not exist" in result.output or "ERROR" in result.output


def test_audit_config_flag_threaded_to_config_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """zenzic audit --config PATH loads that exact file instead of discovering .zenzic.toml."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "right_docs").mkdir()
    (tmp_path / "right_docs" / "index.md").write_text("# Right\n")
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "wrong_docs"\n')
    override_config = tmp_path / "prod.toml"
    override_config.write_text('docs_dir = "right_docs"\n')

    result = runner.invoke(app, ["audit", "--config", str(override_config), "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    # docs_dir "wrong_docs" (from .zenzic.toml) does not exist on disk at all — if
    # the override config file were ignored, this would find 0 files, not 1.
    assert payload["executive_summary"]["total_files"] == 1


# ---------------------------------------------------------------------------
# GAP-04: check all --strict + --exit-zero are mutually exclusive
# ---------------------------------------------------------------------------


def test_check_all_strict_exit_zero_conflict_exits_1() -> None:
    """--strict and --exit-zero together is a plain CLI-usage error: exit 1, not Exit 2."""
    result = runner.invoke(app, ["check", "all", "--strict", "--exit-zero"])
    assert result.exit_code == 1, result.output
    assert "mutually exclusive" in result.output.lower() or "exclusive" in result.output.lower()


@patch("zenzic.cli._check._collect_all_results", return_value=[])
def test_check_all_strict_alone_does_not_conflict(_mock_collect) -> None:
    """--strict alone must NOT trigger the conflict guard (flag is parsed without error)."""
    result = runner.invoke(app, ["check", "all", "--strict", "--no-external"])
    assert result.exit_code != 2 or "mutually exclusive" not in result.output.lower()


# ---------------------------------------------------------------------------
# GAP-06: exception hardening — RuntimeError from find_repo_root → Exit 1
# ---------------------------------------------------------------------------


@patch("zenzic.cli._check.find_repo_root", side_effect=RuntimeError("no .git found"))
def test_check_all_runtime_error_exits_1(_root) -> None:
    """RuntimeError from find_repo_root in check all must produce Exit 1 + ERROR message."""
    result = runner.invoke(app, ["check", "all"])
    assert result.exit_code == 1, result.output
    assert "ERROR" in result.output or "error" in result.output.lower()


@patch("zenzic.cli._standalone.find_repo_root", side_effect=RuntimeError("no .git found"))
def test_score_runtime_error_exits_1(_root) -> None:
    """RuntimeError from find_repo_root in score must produce Exit 1 + ERROR message."""
    result = runner.invoke(app, ["score"])
    assert result.exit_code == 1, result.output
    assert "ERROR" in result.output or "error" in result.output.lower()


@patch("zenzic.cli._standalone.find_repo_root", side_effect=RuntimeError("no .git found"))
def test_diff_runtime_error_exits_1(_root) -> None:
    """RuntimeError from find_repo_root in diff must produce Exit 1 + ERROR message."""
    result = runner.invoke(app, ["diff"])
    assert result.exit_code == 1, result.output
    assert "ERROR" in result.output or "error" in result.output.lower()


@patch("zenzic.cli._command_setup.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, False))
@patch(
    "zenzic.cli._check.validate_links_structured",
    return_value=[
        LinkError(
            file_path=_ROOT / "docs" / "index.md",
            line_no=1,
            message="circular link",
            source_line="[foo](foo.md)",
            error_type="Z106",
        )
    ],
)
def test_check_links_circular_link_note_strict_exits_0(_links, _cfg, _root) -> None:
    """Z106 circular link note must not fail check links under --strict."""
    result = runner.invoke(app, ["check", "links", "--strict"])
    assert result.exit_code == 0


@patch("zenzic.cli._shared._count_docs_assets", return_value=(5, 0))
@patch("zenzic.cli._check.find_repo_root", return_value=_ROOT)
@patch("zenzic.cli._check.ZenzicConfig.load", return_value=(_CFG, True))
@patch("zenzic.cli._check.validate_links_structured", return_value=[])
@patch("zenzic.cli._check.find_orphans", return_value=[])
@patch("zenzic.cli._check.validate_snippets", return_value=[])
@patch("zenzic.cli._check.find_unused_assets", return_value=[])
@patch("zenzic.cli._check.check_nav_contract", return_value=[])
@patch("zenzic.cli._check.scan_docs_references", return_value=([], []))
def test_check_all_progress_bar_activation(
    mock_scan, _nav, _assets, _snip, _orphans, _links, _cfg, _root, _count
) -> None:
    """Verify that progress bar show_progress parameter obeys strict gate rules."""
    runner.invoke(app, ["check", "all"])
    mock_scan.assert_called_with(
        ANY,
        ANY,
        config=ANY,
        validate_links=ANY,
        locale_roots=ANY,
        content_roots=ANY,
        show_progress=True,
        progress_instance=ANY,
        rule_engine_target=ANY,
    )
    mock_scan.reset_mock()

    runner.invoke(app, ["check", "all", "--no-header"])
    mock_scan.assert_called_with(
        ANY,
        ANY,
        config=ANY,
        validate_links=ANY,
        locale_roots=ANY,
        content_roots=ANY,
        show_progress=False,
        progress_instance=None,
        rule_engine_target=ANY,
    )
    mock_scan.reset_mock()

    runner.invoke(app, ["check", "all", "--ci"])
    mock_scan.assert_called_with(
        ANY,
        ANY,
        config=ANY,
        validate_links=ANY,
        locale_roots=ANY,
        content_roots=ANY,
        show_progress=False,
        progress_instance=None,
        rule_engine_target=ANY,
    )


def test_templates_root_keys_not_swallowed() -> None:
    """Ensure root keys like excluded_dirs are not swallowed by tables in TOML templates."""
    import re
    import sys

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    from zenzic.cli.templates import GLOBAL_TOML_TEMPLATE, LOCAL_TOML_TEMPLATE

    # Test global template: we uncomment specific root keys to ensure they parse into the root dict.
    for key in ["excluded_dirs", "forbidden_patterns", "plugins", "docs_dir"]:
        # Uncomment the key
        template = re.sub(rf"(?m)^#\s*({key}\s*=.*)", r"\1", GLOBAL_TOML_TEMPLATE)
        template = template.format(engine="standalone", hint_name="test")

        data = tomllib.loads(template)
        assert key in data, f"'{key}' was swallowed by a table in GLOBAL_TOML_TEMPLATE!"

    # Test local template: forbidden_patterns is already uncommented
    local_data = tomllib.loads(LOCAL_TOML_TEMPLATE)
    assert "forbidden_patterns" in local_data, (
        "'forbidden_patterns' was swallowed in LOCAL_TOML_TEMPLATE!"
    )


def test_check_all_only_filter_excludes_z118(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that zenzic check all --only z101 excludes Z620 warnings."""
    monkeypatch.chdir(tmp_path)
    from typer.testing import CliRunner

    from zenzic.main import app

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Test\n[Valid](index.md)\n", encoding="utf-8")

    toml = tmp_path / ".zenzic.toml"
    toml.write_text(
        '[governance]\ndirectory_policies = {"docs/unused/**" = ["Z405"]}\n',
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["check", "all", "--only", "z101", "--no-header"],
        catch_exceptions=False,
    )
    assert "Z620" not in result.output


def test_env_command() -> None:
    """Verify zenzic env outputs human-readable environment diagnostics."""
    from typer.testing import CliRunner

    from zenzic.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["env"])
    assert result.exit_code == 0
    assert "Zenzic Environment Diagnostics" in result.stdout
    assert "Zenzic Version:" in result.stdout
    assert "Python Executable:" in result.stdout
    assert "Zenzic Module Path:" in result.stdout
    assert "Working Directory:" in result.stdout


def test_env_command_json() -> None:
    """Verify zenzic env --json outputs structured JSON environment diagnostics."""
    import json

    from typer.testing import CliRunner

    from zenzic.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["env", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "zenzic_version" in data
    assert "python_executable" in data
    assert "zenzic_module_path" in data
    assert "current_working_directory" in data
    assert "active_config_path" in data
