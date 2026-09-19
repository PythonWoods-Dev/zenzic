# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Phase 2 Truth-Seeker tests: Sovereign Audit and Secret Guard."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from zenzic.cli._governance import _apply_directory_policies, _apply_per_file_ignores
from zenzic.core.reporter import Finding
from zenzic.core.sovereign_context import sovereign_context
from zenzic.core.suppressions import SuppressionTracker, count_inline_suppressions
from zenzic.main import app
from zenzic.models.config import GovernanceConfig, ZenzicConfig


runner = CliRunner()


def test_inline_suppression_is_ignored_in_sovereign_audit_mode() -> None:
    line = "Legacy name <!-- zenzic:ignore: Z601 - historical -->"
    assert SuppressionTracker(Path("docs/page.md"), line).is_suppressed(1, "Z601") is True

    with sovereign_context(force_audit=True):
        assert SuppressionTracker(Path("docs/page.md"), line).is_suppressed(1, "Z601") is False


def test_per_file_ignores_are_disabled_in_sovereign_audit_mode() -> None:
    findings = [
        Finding(
            rel_path="docs/example.md",
            line_no=12,
            code="Z601",
            severity="warning",
            message="obsolete brand",
        )
    ]
    config = ZenzicConfig(governance=GovernanceConfig(per_file_ignores={"docs/*.md": ["Z601"]}))

    normal = _apply_per_file_ignores(findings, config)
    assert normal == []

    with sovereign_context(force_audit=True):
        audited = _apply_per_file_ignores(findings, config)
    assert len(audited) == 1
    assert audited[0].code == "Z601"


def test_guard_scan_detects_secrets_and_exits_2(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".zenzic.toml").write_text("docs_dir = '.'\n", encoding="utf-8")
    bad = repo / "README.md"
    bad.write_text("token = ghp_abcdefghijklmnopqrstuvwxyz1234567890", encoding="utf-8")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["guard", "scan", "README.md"])
    assert result.exit_code == 2, result.output
    assert "github-token" in result.output


def test_guard_scan_clean_exit_zero(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".zenzic.toml").write_text("docs_dir = '.'\n", encoding="utf-8")
    ok = repo / "README.md"
    ok.write_text("No credentials here.", encoding="utf-8")
    monkeypatch.chdir(repo)

    result = runner.invoke(app, ["guard", "scan", "README.md"])
    assert result.exit_code == 0, result.output
    assert "Secret Guard clean" in result.output


def test_guard_init_writes_hook_and_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)

    first = runner.invoke(app, ["guard", "init"])
    assert first.exit_code == 0, first.output
    hooks = repo / ".pre-commit-hooks.yaml"
    content = hooks.read_text(encoding="utf-8")
    assert "- id: zenzic-guard" in content

    second = runner.invoke(app, ["guard", "init"])
    assert second.exit_code == 0, second.output
    content_after = hooks.read_text(encoding="utf-8")
    assert content_after.count("- id: zenzic-guard") == 1


# ── ADR-084: Fence-aware count_inline_suppressions ────────────────────────────


def test_count_inline_suppressions_skips_fenced_code_blocks() -> None:
    """Suppressions inside triple-backtick fences must not be counted."""
    text = (
        "Here is an example:\n"
        "```markdown\n"
        "<!-- zenzic:ignore: Z601 - inside fence -->\n"
        "{/* zenzic:ignore: Z601 - also inside fence */}\n"
        "```\n"
        "Normal prose continues here.\n"
    )
    assert count_inline_suppressions(text) == 0


def test_count_inline_suppressions_skips_inline_code_spans() -> None:
    """Suppressions inside backtick inline code spans must not be counted."""
    text = "Use `<!-- zenzic:ignore: Z601 -->` or `{/* zenzic:ignore: Z601 */}` in your file.\n"
    assert count_inline_suppressions(text) == 0


def test_count_inline_suppressions_counts_active_prose() -> None:
    """Bare suppression directives in prose must be counted."""
    text = (
        "Obsidian was the v0.6.x codename. <!-- zenzic:ignore: Z601 - historical -->\n"
        "Another line without suppression.\n"
    )
    assert count_inline_suppressions(text) == 1


# ── ADR-084: _apply_directory_policies ────────────────────────────────────────


def _make_finding(rel_path: str, code: str = "Z601") -> Finding:
    return Finding(
        rel_path=rel_path,
        line_no=1,
        code=code,
        severity="warning",
        message="test finding",
    )


def test_apply_directory_policies_filters_findings_normal_mode() -> None:
    """Exempt findings are silently dropped in normal mode — zero debt."""
    findings = [_make_finding("blog/post.mdx", "Z601")]
    config = ZenzicConfig(governance=GovernanceConfig(directory_policies={"blog/**": ["Z601"]}))
    result = _apply_directory_policies(findings, config)
    assert result == []


def test_apply_directory_policies_shows_policy_exemption_label_in_audit_mode() -> None:
    """In audit mode, exempt findings are kept with [POLICY_EXEMPTION] prefix."""
    findings = [_make_finding("blog/post.mdx", "Z601")]
    config = ZenzicConfig(governance=GovernanceConfig(directory_policies={"blog/**": ["Z601"]}))
    with sovereign_context(force_audit=True):
        result = _apply_directory_policies(findings, config)
    assert len(result) == 1
    assert result[0].message.startswith("[POLICY_EXEMPTION]")


def test_apply_directory_policies_never_suppresses_security_codes() -> None:
    """Security findings (Z201-Z204) must bypass directory_policies unconditionally."""
    findings = [_make_finding("blog/post.mdx", "Z201")]
    config = ZenzicConfig(governance=GovernanceConfig(directory_policies={"blog/**": ["Z201"]}))
    result = _apply_directory_policies(findings, config)
    assert len(result) == 1
    assert result[0].code == "Z201"
