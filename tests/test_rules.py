# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for the Zenzic Rule Engine: BaseRule, CustomRule, AdaptiveRuleEngine."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from _helpers import make_mgr

from zenzic.core.exceptions import PluginContractError
from zenzic.core.rules import (
    AdaptiveRuleEngine,
    BaseRule,
    BrandObsolescenceRule,
    CircularAnchorRule,
    CustomRule,
    MalformedFrontmatterRule,
    PluginRegistry,
    RuleFinding,
    UntaggedCodeBlockRule,
    Violation,
    VSMBrokenLinkRule,
    _extract_inline_links_with_lines,
)
from zenzic.models.config import CustomRuleConfig, ProjectMetadata, ZenzicConfig
from zenzic.models.vsm import Route


_FILE = Path("docs/guide.md")


# Module-level BrokenRule: pickleable (defined at module level) but raises
# at runtime inside check().  Tests that the engine isolates runtime errors.
class _BrokenRule(BaseRule):
    @property
    def rule_id(self) -> str:
        return "ZZ-BROKEN"

    def check(self, file_path: Path, text: str) -> list[RuleFinding]:
        raise RuntimeError("rule internal error")


class _PluginTodoRule(BaseRule):
    @property
    def rule_id(self) -> str:
        return "PLUG-TODO"

    def check(self, file_path: Path, text: str) -> list[RuleFinding]:
        findings: list[RuleFinding] = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            if "PLUGIN_TODO" in line:
                findings.append(
                    RuleFinding(
                        file_path=file_path,
                        line_no=line_no,
                        rule_id=self.rule_id,
                        message="Plugin TODO marker found.",
                        severity="error",
                        matched_line=line,
                    )
                )
        return findings


# Module-level BrokenVsmRule: pickleable but raises in check_vsm().
class _BrokenVsmRule(BaseRule):
    @property
    def rule_id(self) -> str:
        return "ZZ-BROKEN-VSM"

    def check(self, file_path: Path, text: str) -> list[RuleFinding]:
        return []

    def check_vsm(self, file_path, text, vsm, anchors_cache, context=None) -> list[Violation]:
        raise RuntimeError("vsm rule internal error")


# ─── CustomRule ───────────────────────────────────────────────────────────────


def test_custom_rule_single_match() -> None:
    rule = CustomRule(id="ZZ001", pattern=r"TODO", message="Remove TODO.", severity="warning")
    findings = rule.check(_FILE, "Line one.\nTODO: fix this.\nLine three.\n")
    assert len(findings) == 1
    assert findings[0].line_no == 2
    assert findings[0].rule_id == "ZZ001"
    assert findings[0].severity == "warning"
    assert not findings[0].is_error


def test_custom_rule_multiple_matches() -> None:
    rule = CustomRule(id="ZZ002", pattern=r"(?i)\bDRAFT\b", message="Draft.", severity="error")
    text = "DRAFT intro.\nNormal line.\ndraft section.\n"
    findings = rule.check(_FILE, text)
    assert len(findings) == 2
    assert {f.line_no for f in findings} == {1, 3}


def test_custom_rule_no_match() -> None:
    rule = CustomRule(id="ZZ003", pattern=r"SECRET", message="Secret.", severity="error")
    findings = rule.check(_FILE, "This text is clean.\nNo issues here.\n")
    assert findings == []


def test_custom_rule_invalid_regex_raises() -> None:
    # ZRT-007: RE2 rejects non-regular and syntactically invalid patterns at
    # construction time with PluginContractError (not ValueError).
    from zenzic.core.exceptions import PluginContractError

    with pytest.raises(PluginContractError, match="RE2"):
        CustomRule(id="ZZ004", pattern=r"[unclosed", message="Bad pattern.", severity="error")


def test_custom_rule_is_error_severity() -> None:
    rule = CustomRule(id="ZZ005", pattern=r"x", message="x found.", severity="error")
    findings = rule.check(_FILE, "x\n")
    assert findings[0].is_error


def test_custom_rule_info_severity_not_error() -> None:
    rule = CustomRule(id="ZZ006", pattern=r"x", message="x found.", severity="info")
    findings = rule.check(_FILE, "x\n")
    assert not findings[0].is_error


def test_custom_rule_no_link_message_unchanged() -> None:
    """A CustomRule with no `link` produces exactly the configured message,
    byte-for-byte — existing rules with no link keep working unchanged."""
    rule = CustomRule(id="ZZ011", pattern=r"TODO", message="Remove TODO.", severity="warning")
    findings = rule.check(_FILE, "TODO: fix this.\n")
    assert findings[0].message == "Remove TODO."


def test_custom_rule_link_appears_in_finding_message() -> None:
    """A CustomRule with `link` set surfaces it in the finding's message."""
    rule = CustomRule(
        id="ZZ012",
        pattern=r"TODO",
        message="Remove TODO.",
        severity="warning",
        link="https://wiki.example.com/todo-policy",
    )
    findings = rule.check(_FILE, "TODO: fix this.\n")
    assert len(findings) == 1
    assert "Remove TODO." in findings[0].message
    assert "https://wiki.example.com/todo-policy" in findings[0].message


# ─── AdaptiveRuleEngine ───────────────────────────────────────────────────────────────


def test_rule_engine_empty_no_findings() -> None:
    engine = AdaptiveRuleEngine([])
    assert not engine
    assert engine.run(_FILE, "any text") == []


def test_rule_engine_bool_true_when_rules_present() -> None:
    rule = CustomRule(id="ZZ007", pattern=r"x", message="x", severity="error")
    engine = AdaptiveRuleEngine([rule])
    assert engine


def test_rule_engine_multiple_rules_combined() -> None:
    r1 = CustomRule(id="ZZ008", pattern=r"TODO", message="todo found", severity="error")
    r2 = CustomRule(id="ZZ009", pattern=r"FIXME", message="fixme found", severity="warning")
    engine = AdaptiveRuleEngine([r1, r2])
    text = "Line with TODO here.\nAnother FIXME line.\n"
    findings = engine.run(_FILE, text)
    assert len(findings) == 2
    rule_ids = {f.rule_id for f in findings}
    assert rule_ids == {"ZZ008", "ZZ009"}


def test_rule_engine_isolates_exception() -> None:
    """A module-level rule that raises at runtime must not abort the engine run.

    _BrokenRule is defined at module level so it passes eager pickle validation.
    Its check() raises at runtime — the engine must catch it and continue.
    """
    good_rule = CustomRule(id="ZZ010", pattern=r"x", message="x found", severity="info")
    engine = AdaptiveRuleEngine([_BrokenRule(), good_rule])
    findings = engine.run(_FILE, "x line\n")

    # One error from the broken rule, one info from the good rule
    assert len(findings) == 2
    engine_err = next(f for f in findings if f.rule_id == "Z901")
    assert "ZZ-BROKEN" in engine_err.message or "rule internal error" in engine_err.message
    assert engine_err.severity == "error"

    good_finding = next(f for f in findings if f.rule_id == "ZZ010")
    assert good_finding.severity == "info"


def test_rule_engine_rejects_non_pickleable_rule() -> None:
    """A rule defined inside a function is not pickleable → PluginContractError at construction."""

    class LocalRule(BaseRule):
        @property
        def rule_id(self) -> str:
            return "ZZ-LOCAL"

        def check(self, file_path: Path, text: str) -> list[RuleFinding]:
            return []

    with pytest.raises(PluginContractError, match="not serialisable"):
        AdaptiveRuleEngine([LocalRule()])


# ─── Integration with scanner ──────────────────────────────────────────────────


def test_scan_single_file_with_rule_engine(tmp_path: Path) -> None:
    """_scan_single_file applies the rule engine and stores findings in the report."""
    from zenzic.core.scanner import _scan_single_file

    md = tmp_path / "guide.md"
    md.write_text("# Guide\n\nThis is TODO content.\n")
    config = ZenzicConfig()
    rule = CustomRule(id="ZZ-TODO", pattern=r"TODO", message="Remove TODO.", severity="warning")
    engine = AdaptiveRuleEngine([rule])

    report, _ = _scan_single_file(md, config, engine)
    assert len(report.rule_findings) == 1
    assert report.rule_findings[0].rule_id == "ZZ-TODO"
    assert report.rule_findings[0].line_no == 3


def test_scan_single_file_no_rule_engine(tmp_path: Path) -> None:
    """Without a rule engine, rule_findings is empty."""
    from zenzic.core.scanner import _scan_single_file

    md = tmp_path / "guide.md"
    md.write_text("# Guide\n\nTODO: fix\n")
    config = ZenzicConfig()

    report, _ = _scan_single_file(md, config, None)
    assert report.rule_findings == []


def test_scan_docs_with_custom_rules_from_config(tmp_path: Path) -> None:
    """scan_docs_references picks up [[custom_rules]] from config."""
    from zenzic.core.scanner import scan_docs_references

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(
        "# Page\n\nPlease remove DRAFT marker. " + " ".join(["filler"] * 50) + "\n"
    )

    config = ZenzicConfig(
        custom_rules=[
            CustomRuleConfig(
                id="ZZ-DRAFT",
                pattern=r"(?i)\bDRAFT\b",
                message="Remove DRAFT.",
                severity="error",
            )
        ]
    )
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    reports, _ = scan_docs_references(docs_root, mgr, config=config)
    assert len(reports) == 1
    draft_findings = [f for f in reports[0].rule_findings if f.rule_id == "ZZ-DRAFT"]
    assert len(draft_findings) == 1
    assert draft_findings[0].rule_id == "ZZ-DRAFT"


def test_build_rule_engine_always_built() -> None:
    """Engine is always built: Z107, Z505, and Z506 are always-active built-in rules."""
    from zenzic.core.scanner import _build_rule_engine

    config = ZenzicConfig()
    engine = _build_rule_engine(config)
    assert engine is not None
    rule_ids = {r.rule_id for r in engine._rules}
    assert "Z107" in rule_ids
    assert "Z505" in rule_ids


def test_scan_docs_with_enabled_plugins_from_config(tmp_path: Path) -> None:
    """plugins=[...] activates external plugin rules during scanning."""
    from zenzic.core.scanner import scan_docs_references

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(
        "# Page\n\nPLUGIN_TODO marker. " + " ".join(["filler"] * 50) + "\n"
    )

    config = ZenzicConfig(plugins=["acme-todo"])

    with (
        patch("zenzic.core.rules.PluginRegistry.load_core_rules", return_value=[]),
        patch(
            "zenzic.core.rules.PluginRegistry.load_selected_rules",
            return_value=[_PluginTodoRule()],
        ),
    ):
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        reports, _ = scan_docs_references(docs_root, mgr, config=config)

    assert len(reports) == 1
    plugin_findings = [f for f in reports[0].rule_findings if f.rule_id == "PLUG-TODO"]
    assert len(plugin_findings) == 1
    assert plugin_findings[0].rule_id == "PLUG-TODO"
    assert plugin_findings[0].message == "Plugin TODO marker found."


def test_scan_docs_with_unknown_plugin_raises_contract_error(tmp_path: Path) -> None:
    """Unknown plugin IDs in config.plugins fail fast with a clear error."""
    from zenzic.core.scanner import scan_docs_references

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("# Page\n")

    config = ZenzicConfig(plugins=["does-not-exist"])
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    with pytest.raises(PluginContractError, match="Configured plugin rule IDs were not found"):
        scan_docs_references(docs_root, mgr, config=config)


def test_plugin_registry_deduplicates_requested_plugin_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duplicate plugin IDs are loaded once while preserving declaration order."""

    class _EP:
        def __init__(self, name: str) -> None:
            self.name = name

    registry = PluginRegistry()
    monkeypatch.setattr(
        registry,
        "_entry_points",
        lambda: [_EP("acme"), _EP("beta")],
    )

    loaded_names: list[str] = []

    def _fake_load(ep: _EP, *_args: object, **_kwargs: object) -> BaseRule:
        loaded_names.append(ep.name)
        return _PluginTodoRule()

    monkeypatch.setattr(registry, "_load_entry_point", _fake_load)

    _rules = registry.load_selected_rules(["acme", "acme", "beta", "acme"])  # noqa: F841
    assert loaded_names == ["acme", "beta"]


# ─── Cross-adapter custom rules (Dev 4 mandate) ───────────────────────────────


def _make_repo_with_draft(tmp_path: Path) -> Path:
    """Create a minimal repo with a single docs/page.md containing 'DRAFT'."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(
        "# Page\n\nThis is a DRAFT page. " + " ".join(["filler"] * 50) + "\n"
    )
    return tmp_path


def _draft_rule_config() -> ZenzicConfig:
    return ZenzicConfig(
        custom_rules=[
            CustomRuleConfig(
                id="ZZ-DRAFT",
                pattern=r"(?i)\bDRAFT\b",
                message="Remove DRAFT marker before publishing.",
                severity="error",
            )
        ]
    )


@pytest.mark.parametrize("engine", ["mkdocs", "zensical", "auto"])
def test_custom_rules_fire_regardless_of_engine(
    tmp_path: Path,
    engine: str,
) -> None:
    """Dev 4 mandate: [[custom_rules]] must fire identically for every adapter.

    The rule engine operates on raw Markdown text — it has no knowledge of the
    build engine.  This test verifies that the DRAFT rule is triggered whether
    the adapter is MkDocs, Zensical, or StandaloneAdapter (auto-detected).
    """
    from zenzic.core.scanner import scan_docs_references

    repo = _make_repo_with_draft(tmp_path)

    # Build a config that selects the requested adapter via build_context.engine.
    # For "auto" no engine override is needed — StandaloneAdapter will be selected
    # because no mkdocs.yml or zensical.toml is present.
    base_config = _draft_rule_config()
    if engine != "auto":
        new_context = base_config.build_context.model_copy(update={"engine": engine})
        config: ZenzicConfig = base_config.model_copy(update={"build_context": new_context})
    else:
        config = base_config

    # For zensical engine, a zensical.toml must exist (factory enforcement contract).
    if engine == "zensical":
        (repo / "zensical.toml").write_text("[site]\nname = 'Test'\n")

    docs_root = repo / config.docs_dir
    mgr = make_mgr(config, repo_root=repo)
    reports, _ = scan_docs_references(docs_root, mgr, config=config)
    assert len(reports) == 1, f"Expected 1 report for engine={engine!r}"
    draft_findings = [f for f in reports[0].rule_findings if f.rule_id == "ZZ-DRAFT"]
    assert len(draft_findings) == 1, (
        f"Expected 1 ZZ-DRAFT finding for engine={engine!r}, got {reports[0].rule_findings}"
    )
    assert draft_findings[0].rule_id == "ZZ-DRAFT"
    assert draft_findings[0].is_error


# ─── Violation dataclass ──────────────────────────────────────────────────────


class TestViolation:
    """🎨 Dev 2: verify the Violation contract (code, level, context)."""

    def test_violation_fields(self) -> None:
        v = Violation(
            file_path=_FILE,
            line_no=5,
            code="Z101",
            message="Broken link.",
            level="error",
            context="[bad link](missing.md)",
        )
        assert v.code == "Z101"
        assert v.level == "error"
        assert v.context == "[bad link](missing.md)"
        assert v.is_error

    def test_violation_warning_not_error(self) -> None:
        v = Violation(file_path=_FILE, line_no=1, code="Z103", message="hint", level="warning")
        assert not v.is_error

    def test_violation_as_finding_round_trip(self) -> None:
        v = Violation(
            file_path=_FILE,
            line_no=3,
            code="Z101",
            message="msg",
            level="error",
            context="src",
        )
        f = v.as_finding()
        assert isinstance(f, RuleFinding)
        assert f.rule_id == "Z101"
        assert f.line_no == 3
        assert f.matched_line == "src"
        assert f.severity == "error"


# ─── VSMBrokenLinkRule ────────────────────────────────────────────────────────


def _make_vsm(*urls: str, status: str = "REACHABLE") -> dict[str, Route]:
    """Build a minimal VSM dict with the given URL slugs."""
    return {
        url: Route(url=url, source=f"{url.strip('/')}.md", status=status)  # type: ignore[arg-type]
        for url in urls
    }


class TestVSMBrokenLinkRule:
    """🔌 Dev 3: VSM-aware link validation."""

    _RULE = VSMBrokenLinkRule()
    _EMPTY_ANCHORS: dict[Path, set[str]] = {}

    def _run(self, text: str, vsm: dict) -> list[Violation]:  # type: ignore[type-arg]
        return self._RULE.check_vsm(_FILE, text, vsm, self._EMPTY_ANCHORS)

    # ── check() is a no-op ────────────────────────────────────────────────────

    def test_check_returns_empty(self) -> None:
        assert self._RULE.check(_FILE, "[link](page.md)") == []

    # ── REACHABLE link → no violation ─────────────────────────────────────────

    def test_reachable_link_passes(self) -> None:
        vsm = _make_vsm("/guide/")
        violations = self._run("[Guide](guide/index.md)", vsm)
        assert violations == []

    def test_reachable_page_without_md_suffix(self) -> None:
        vsm = _make_vsm("/guide/install/")
        violations = self._run("[Install](guide/install)", vsm)
        assert violations == []

    # ── Missing from VSM → violation ─────────────────────────────────────────

    def test_missing_url_emits_violation(self) -> None:
        violations = self._run("[Broken](missing.md)", {})
        assert len(violations) == 1
        assert violations[0].code == "Z101"
        assert "missing" in violations[0].message
        assert "missing.md" in violations[0].context

    def test_html_broken_link_emits_violation(self) -> None:
        violations = self._run('<a href="missing.html">HTML link</a>', {})
        assert len(violations) == 1
        assert violations[0].code == "Z101"
        assert "missing" in violations[0].message

    # ── ORPHAN status → Z002 warning ─────────────────────────────────────────

    def test_orphan_link_emits_z002_warning(self) -> None:
        vsm = _make_vsm("/draft/", status="ORPHAN_BUT_EXISTING")
        violations = self._run("[Draft](draft.md)", vsm)
        assert len(violations) == 1
        assert violations[0].code == "Z103"
        assert violations[0].level == "warning"
        assert "ORPHAN_LINK" in violations[0].message

    # ── External links are skipped ────────────────────────────────────────────

    def test_external_http_skipped(self) -> None:
        violations = self._run("[Ext](https://example.com)", {})
        assert violations == []

    def test_external_mailto_skipped(self) -> None:
        violations = self._run("[Mail](mailto:user@example.com)", {})
        assert violations == []

    # ── Bare fragment skipped ─────────────────────────────────────────────────

    def test_bare_fragment_skipped(self) -> None:
        violations = self._run("[Top](#top)", {})
        assert violations == []

    # ── Code blocks are skipped ───────────────────────────────────────────────

    def test_link_inside_fenced_block_skipped(self) -> None:
        text = "```\n[broken](totally-missing.md)\n```"
        violations = self._run(text, {})
        assert violations == []

    # ── Violation carries source context ──────────────────────────────────────

    def test_violation_context_is_source_line(self) -> None:
        violations = self._run("See [this](gone.md) for details.", {})
        assert len(violations) == 1
        assert "gone.md" in violations[0].context

    def test_violation_line_number_is_correct(self) -> None:
        text = "# Heading\n\nSome text.\n\n[Broken](ghost.md)\n"
        violations = self._run(text, {})
        assert len(violations) == 1
        assert violations[0].line_no == 5

    # ── AdaptiveRuleEngine.run_vsm integration ───────────────────────────────────────

    def test_run_vsm_converts_violations_to_findings(self) -> None:
        engine = AdaptiveRuleEngine([VSMBrokenLinkRule()])
        vsm = _make_vsm("/ok/")
        findings = engine.run_vsm(_FILE, "[OK](ok/index.md)\n[Bad](ghost.md)\n", vsm, {})
        assert len(findings) == 1
        assert findings[0].rule_id == "Z101"
        assert isinstance(findings[0], RuleFinding)


# ─── Dev 4: O(N) Torture Test — Rule Engine scalability ──────────────────────
# Invariant: VSMBrokenLinkRule.check_vsm must complete in O(N) time where N
# is the number of VSM nodes.  The test builds a 10 000-node VSM and a file
# with 10 000 links and verifies the runtime is < 1 s (far below the O(N²)
# threshold, which would be ~100× slower on this data size).


class TestAdaptiveRuleEngineTortureTest:
    """🛡️ Dev 4: Performance and scalability invariants for the Rule Engine."""

    _N = 10_000

    def _make_large_vsm(self) -> dict[str, Route]:
        return {
            f"/page-{i}/": Route(
                url=f"/page-{i}/",
                source=f"page-{i}.md",
                status="REACHABLE",
            )
            for i in range(self._N)
        }

    def _make_text_with_links(self, n: int, *, all_valid: bool) -> str:
        """Generate a Markdown file with *n* inline links.

        When *all_valid* is True, every link points to a known VSM page.
        When False, all links point to missing pages (worst-case violation path).
        """
        lines = []
        for i in range(n):
            if all_valid:
                lines.append(f"[Page {i}](page-{i}.md)")
            else:
                lines.append(f"[Page {i}](missing-{i}.md)")
        return "\n".join(lines)

    def test_check_vsm_scales_linearly_all_valid(self) -> None:
        """10 000 REACHABLE links must resolve in < 1.5 s (O(N) dict lookups)."""
        rule = VSMBrokenLinkRule()
        vsm = self._make_large_vsm()
        text = self._make_text_with_links(self._N, all_valid=True)

        start = time.monotonic()
        violations = rule.check_vsm(_FILE, text, vsm, {})
        elapsed = time.monotonic() - start

        max_elapsed = 3.0 if sys.platform == "win32" or os.environ.get("CI") else 1.5
        assert violations == [], f"Expected 0 violations, got {len(violations)}"
        assert elapsed < max_elapsed, (
            f"check_vsm took {elapsed:.3f}s for {self._N} valid links — possible O(N²) regression"
        )

    def test_check_vsm_scales_linearly_all_missing(self) -> None:
        """10 000 missing links (worst-case violation path) must complete < 1.5 s."""
        rule = VSMBrokenLinkRule()
        vsm = self._make_large_vsm()
        text = self._make_text_with_links(self._N, all_valid=False)

        start = time.monotonic()
        violations = rule.check_vsm(_FILE, text, vsm, {})
        elapsed = time.monotonic() - start

        max_elapsed = 3.0 if sys.platform == "win32" or os.environ.get("CI") else 1.5
        assert len(violations) == self._N, f"Expected {self._N} violations, got {len(violations)}"
        assert elapsed < max_elapsed, (
            f"check_vsm took {elapsed:.3f}s for {self._N} missing links — possible O(N²) regression"
        )

    def test_run_vsm_engine_scales_with_large_vsm(self) -> None:
        """AdaptiveRuleEngine.run_vsm with 10 000-node VSM must complete < 0.5 s."""
        engine = AdaptiveRuleEngine([VSMBrokenLinkRule()])
        vsm = self._make_large_vsm()
        # Small file — only the VSM lookup overhead is being measured here
        text = "\n".join(f"[P](page-{i}.md)" for i in range(100))

        start = time.monotonic()
        findings = engine.run_vsm(_FILE, text, vsm, {})
        elapsed = time.monotonic() - start

        max_elapsed = 1.5 if sys.platform == "win32" or os.environ.get("CI") else 0.5
        assert findings == []
        assert elapsed < max_elapsed, (
            f"run_vsm took {elapsed:.3f}s with {self._N}-node VSM — regression"
        )


# ─── Public namespace & run_rule helper ───────────────────────────────────────


class TestPublicNamespace:
    """Issue #13: zenzic.rules must be a stable public import path."""

    def test_import_base_rule(self) -> None:
        from zenzic.rules import BaseRule as PublicBaseRule

        assert PublicBaseRule is BaseRule

    def test_import_rule_finding(self) -> None:
        from zenzic.rules import RuleFinding as PublicRuleFinding

        assert PublicRuleFinding is RuleFinding

    def test_import_custom_rule(self) -> None:
        from zenzic.rules import CustomRule as PublicCustomRule

        assert PublicCustomRule is CustomRule

    def test_run_rule_helper(self) -> None:
        from zenzic.rules import run_rule

        rule = CustomRule(id="TEST-001", pattern=r"FIXME", message="Fix it.", severity="warning")
        findings = run_rule(rule, "Line 1\nFIXME here\nLine 3")
        assert len(findings) == 1
        assert findings[0].rule_id == "TEST-001"
        assert findings[0].severity == "warning"
        assert findings[0].line_no == 2

    def test_run_rule_no_findings(self) -> None:
        from zenzic.rules import run_rule

        rule = CustomRule(id="TEST-002", pattern=r"BANANA", message="No bananas.")
        findings = run_rule(rule, "Clean content here.")
        assert findings == []


# ─── Mutant-Killing Tests: _extract_inline_links_with_lines ──────────────────


class TestExtractInlineLinksWithLines:
    """Kill mutants in the _extract_inline_links_with_lines utility."""

    def test_simple_link_extraction(self) -> None:
        text = "[Foo](bar.md)"
        result = _extract_inline_links_with_lines(text)
        assert len(result) == 1
        url, lineno, raw = result[0]
        assert url == "bar.md"
        assert lineno == 1
        assert "bar.md" in raw

    def test_multiple_links_all_extracted(self) -> None:
        """Multiple links on different lines — kills continue→break mutations."""
        text = "[A](a.md)\n[B](b.md)\n[C](c.md)"
        result = _extract_inline_links_with_lines(text)
        assert len(result) == 3
        urls = [r[0] for r in result]
        assert urls == ["a.md", "b.md", "c.md"]

    def test_line_numbers_correct_multiline(self) -> None:
        text = "Preamble.\n\n[Link](page.md)\n\nEnd."
        result = _extract_inline_links_with_lines(text)
        assert len(result) == 1
        assert result[0][1] == 3

    def test_fenced_block_skips_links(self) -> None:
        text = "```\n[fake](ghost.md)\n```"
        result = _extract_inline_links_with_lines(text)
        assert result == []

    def test_tilde_fence_block_skips_links(self) -> None:
        text = "~~~\n[fake](ghost.md)\n~~~"
        result = _extract_inline_links_with_lines(text)
        assert result == []

    def test_link_before_and_after_fence_both_found(self) -> None:
        """Both links around a fence block are found — kills in_block=None mutation."""
        text = "[A](a.md)\n```\n[B](b.md)\n```\n[C](c.md)"
        result = _extract_inline_links_with_lines(text)
        assert len(result) == 2
        urls = [r[0] for r in result]
        assert urls == ["a.md", "c.md"]

    def test_inline_code_link_ignored(self) -> None:
        text = "See `[link](code.md)` for details."
        result = _extract_inline_links_with_lines(text)
        assert result == []

    def test_mixed_inline_code_and_real_link(self) -> None:
        text = "`[a](a.md)` and [b](b.md)"
        result = _extract_inline_links_with_lines(text)
        assert len(result) == 1
        assert result[0][0] == "b.md"

    def test_link_with_title_stripped(self) -> None:
        text = '[Link](page.md "Title text")'
        result = _extract_inline_links_with_lines(text)
        assert len(result) == 1
        assert result[0][0] == "page.md"

    def test_empty_url_skipped(self) -> None:
        text = "[Empty]()"
        result = _extract_inline_links_with_lines(text)
        assert result == []

    def test_image_link_extracted(self) -> None:
        text = "![Alt](image.png)"
        result = _extract_inline_links_with_lines(text)
        assert len(result) == 1
        assert result[0][0] == "image.png"

    def test_multiple_links_after_fence_all_found(self) -> None:
        """After a fenced block ends, ALL subsequent links must be found (not just first)."""
        text = "```\ncode\n```\n[A](a.md)\n[B](b.md)\n[C](c.md)"
        result = _extract_inline_links_with_lines(text)
        assert len(result) == 3

    def test_empty_input_returns_empty(self) -> None:
        assert _extract_inline_links_with_lines("") == []

    def test_no_links_returns_empty(self) -> None:
        assert _extract_inline_links_with_lines("Just plain text.") == []

    def test_whitespace_only_url_skipped(self) -> None:
        text = "[Space](   )"
        result = _extract_inline_links_with_lines(text)
        assert result == []


# ─── Mutant-Killing Tests: VSMBrokenLinkRule.check_vsm deep assertions ──────


class TestVSMBrokenLinkRuleMutantKill:
    """Kill mutants in VSMBrokenLinkRule.check_vsm with precise assertions."""

    _RULE = VSMBrokenLinkRule()
    _EMPTY_ANCHORS: dict[Path, set[str]] = {}

    def _run(self, text: str, vsm: dict, file_path: Path = _FILE) -> list[Violation]:  # type: ignore[type-arg]
        return self._RULE.check_vsm(file_path, text, vsm, self._EMPTY_ANCHORS)

    # ── Exact field assertions on violations (kill string mutations) ──────────

    def test_missing_link_violation_exact_fields(self) -> None:
        """Assert every field of a Z101 violation — kills all string/field mutations."""
        violations = self._run("[Bad](ghost.md)", {})
        assert len(violations) == 1
        v = violations[0]
        assert v.file_path == _FILE
        assert v.line_no == 1
        assert v.code == "Z101"
        assert v.level == "error"
        assert v.is_error
        assert "ghost.md" in v.message
        assert "Virtual Site Map" in v.message
        assert "ghost.md" in v.context

    def test_orphan_violation_exact_fields(self) -> None:
        """Assert every field of a Z002 violation."""
        vsm = _make_vsm("/draft/", status="ORPHAN_BUT_EXISTING")
        violations = self._run("[Draft](draft.md)", vsm)
        assert len(violations) == 1
        v = violations[0]
        assert v.file_path == _FILE
        assert v.line_no == 1
        assert v.code == "Z103"
        assert v.level == "warning"
        assert not v.is_error
        assert "ORPHAN_LINK" in v.message
        assert "not in the site navigation" in v.message
        assert "Readers cannot reach this page via the nav tree." in v.message
        assert "draft.md" in v.context

    def test_unreachable_link_violation_exact_fields(self) -> None:
        """UNREACHABLE status emits error — kills `not in ("REACHABLE",)` mutations."""
        vsm = {"/page/": Route(url="/page/", source="page.md", status="UNREACHABLE")}  # type: ignore[arg-type]
        violations = self._run("[Page](page.md)", vsm)
        assert len(violations) == 1
        v = violations[0]
        assert v.file_path == _FILE
        assert v.code == "Z101"
        assert v.level == "error"
        assert "UNREACHABLE_LINK" in v.message
        assert "'UNREACHABLE'" in v.message

    def test_custom_status_not_reachable_emits_error(self) -> None:
        """Any status other than REACHABLE should trigger an error."""
        vsm = {"/page/": Route(url="/page/", source="page.md", status="SOME_OTHER_STATUS")}  # type: ignore[arg-type]
        violations = self._run("[Page](page.md)", vsm)
        assert len(violations) == 1
        assert violations[0].code == "Z101"

    # ── file_path propagation (kill file_path=None mutations) ────────────────

    def test_violation_carries_correct_file_path(self) -> None:
        custom_file = Path("docs/custom/page.md")
        violations = self._run("[Bad](gone.md)", {}, file_path=custom_file)
        assert len(violations) == 1
        assert violations[0].file_path == custom_file

    def test_orphan_violation_carries_file_path(self) -> None:
        custom_file = Path("docs/deep/nested.md")
        vsm = _make_vsm("/deep/", status="ORPHAN_BUT_EXISTING")
        violations = self._run("[See](deep/index.md)", vsm, file_path=custom_file)
        assert len(violations) == 1
        assert violations[0].file_path == custom_file

    def test_unreachable_violation_carries_file_path(self) -> None:
        custom_file = Path("docs/other.md")
        vsm = {"/target/": Route(url="/target/", source="target.md", status="BLOCKED")}  # type: ignore[arg-type]
        violations = self._run("[T](target.md)", vsm, file_path=custom_file)
        assert len(violations) == 1
        assert violations[0].file_path == custom_file

    # ── Multiple links: continue vs break (kill continue→break) ──────────────

    def test_multiple_broken_links_all_reported(self) -> None:
        """All broken links must be reported, not just the first."""
        text = "[A](a.md)\n[B](b.md)\n[C](c.md)"
        violations = self._run(text, {})
        assert len(violations) == 3
        urls_in_msg = [v.message for v in violations]
        assert any("a.md" in m for m in urls_in_msg)
        assert any("b.md" in m for m in urls_in_msg)
        assert any("c.md" in m for m in urls_in_msg)

    def test_multiple_orphan_links_all_reported(self) -> None:
        vsm = {
            "/a/": Route(url="/a/", source="a.md", status="ORPHAN_BUT_EXISTING"),
            "/b/": Route(url="/b/", source="b.md", status="ORPHAN_BUT_EXISTING"),
        }
        violations = self._run("[A](a.md)\n[B](b.md)", vsm)
        assert len(violations) == 2
        assert all(v.code == "Z103" for v in violations)

    def test_mixed_valid_and_broken_only_broken_reported(self) -> None:
        vsm = _make_vsm("/ok/")
        text = "[OK](ok/index.md)\n[Bad](nope.md)"
        violations = self._run(text, vsm)
        assert len(violations) == 1
        assert "nope.md" in violations[0].message

    # ── Bare fragment "#" vs "#anchor" (kill "#"→"XX#XX" mutations) ──────────

    def test_bare_hash_skipped(self) -> None:
        """Exactly '#' must be skipped — kills `"#"→"XX#XX"` mutant."""
        violations = self._run("[Top](#)", {})
        assert violations == []

    def test_fragment_with_id_skipped(self) -> None:
        """'#heading' must be skipped — kills `startswith("#")→startswith("XX#XX")`."""
        violations = self._run("[See](#installation)", {})
        assert violations == []

    def test_fragment_with_special_chars_skipped(self) -> None:
        violations = self._run("[H](#heading-with-special-chars)", {})
        assert violations == []

    # ── External schemes all skipped (kill scheme mutations) ─────────────────

    def test_all_skip_schemes_individually(self) -> None:
        schemes = [
            "http://example.com",
            "https://example.com",
            "mailto:user@example.com",
            "data:text/html,",
            "ftp:something",
            "tel:+1234567890",
            "javascript:void(0)",
            "irc:freenode",
            "xmpp://jabber.org",
        ]
        for scheme_url in schemes:
            violations = self._run(f"[Link]({scheme_url})", {})
            assert violations == [], f"Scheme {scheme_url} was not skipped"

    # ── Links survive fence blocks (kill break in fence logic) ───────────────

    def test_multiple_links_after_fence_block(self) -> None:
        text = "```\n[fake](ghost.md)\n```\n[A](a.md)\n[B](b.md)"
        violations = self._run(text, {})
        assert len(violations) == 2

    # ── Line number correctness (kill lineno mutations) ──────────────────────

    def test_violation_line_numbers_multi_link(self) -> None:
        text = "# Title\n\n[A](a.md)\n\n[B](b.md)\n"
        violations = self._run(text, {})
        assert len(violations) == 2
        assert violations[0].line_no == 3
        assert violations[1].line_no == 5

    # ── continue→break after skips: links after "#" or schemes still found ──

    def test_broken_link_after_bare_hash(self) -> None:
        """After [Top](#), subsequent broken links must still be found.
        Kills continue→break mutant on url=="#" path."""
        text = "[Top](#)\n[Bad](ghost.md)"
        violations = self._run(text, {})
        assert len(violations) == 1
        assert "ghost.md" in violations[0].message

    def test_broken_link_after_fragment(self) -> None:
        """After [Foo](#anchor), subsequent broken links must still be found.
        Kills continue→break on url.startswith('#') path."""
        text = "[Foo](#anchor)\n[Bad](ghost.md)"
        violations = self._run(text, {})
        assert len(violations) == 1
        assert "ghost.md" in violations[0].message

    def test_broken_link_after_external_scheme(self) -> None:
        """After [Ext](https://...), subsequent broken links must still be found.
        Kills continue→break on SKIP_SCHEMES path."""
        text = "[Ext](https://example.com)\n[Bad](ghost.md)"
        violations = self._run(text, {})
        assert len(violations) == 1
        assert "ghost.md" in violations[0].message

    def test_broken_link_after_null_url(self) -> None:
        """After a link that _to_canonical_url returns None for, others still processed.
        Kills continue→break after target_url is None."""
        # A bare query string like "?foo" won't produce a canonical URL
        text = "[Q](?query)\n[Bad](ghost.md)"
        violations = self._run(text, {})
        assert len(violations) >= 1
        assert any("ghost.md" in v.message for v in violations)

    # ── UNREACHABLE status deep assertions (kill line_no, context, string) ───

    def test_unreachable_violation_all_fields_precise(self) -> None:
        """Assert every field of UNREACHABLE violation, including line_no and context."""
        vsm = {"/page/": Route(url="/page/", source="page.md", status="UNREACHABLE")}  # type: ignore[arg-type]
        text = "Lead text.\n\n[Check](page.md)\n"
        violations = self._run(text, vsm)
        assert len(violations) == 1
        v = violations[0]
        assert v.file_path == _FILE
        assert v.line_no == 3
        assert isinstance(v.line_no, int)
        assert v.code == "Z101"
        assert v.level == "error"
        assert v.context is not None
        assert isinstance(v.context, str)
        assert "page.md" in v.context
        assert "UNREACHABLE_LINK" in v.message
        # Kill XX-wrapper string mutations
        assert v.message.endswith("(UNREACHABLE_LINK)")
        assert "via site navigation" in v.message
        # Kill case mutation
        assert "VIA SITE NAVIGATION" not in v.message

    def test_z101_missing_message_no_xx_wrapper(self) -> None:
        """Kill XX-wrapper mutants on Z101 missing link message."""
        violations = self._run("[Bad](ghost.md)", {})
        v = violations[0]
        assert v.message.endswith("the target file may not exist")
        assert "XX" not in v.message

    def test_multiple_links_mixed_hashes_and_broken(self) -> None:
        """Complex scenario: multiple hash links followed by multiple broken links."""
        text = (
            "[A](#top)\n[B](#section)\n[C](https://external.com)\n[D](ghost1.md)\n[E](ghost2.md)\n"
        )
        violations = self._run(text, {})
        assert len(violations) == 2
        messages = " ".join(v.message for v in violations)
        assert "ghost1.md" in messages
        assert "ghost2.md" in messages


# ─── Mutant-Killing Tests: _extract_inline_links deep (fence/code edge) ──────


class TestExtractLinksDeepMutantKill:
    """Kill remaining mutants in _extract_inline_links_with_lines."""

    def test_links_between_two_fence_blocks(self) -> None:
        """Kill in_block=False→None mutant when exiting first fence.
        Link between two fences must be found."""
        text = "```\ncode1\n```\n[Real](real.md)\n```\ncode2\n```"
        result = _extract_inline_links_with_lines(text)
        assert len(result) == 1
        assert result[0][0] == "real.md"

    def test_links_after_multiple_fence_blocks(self) -> None:
        """Multiple fence blocks followed by multiple links."""
        text = "```\na\n```\n```\nb\n```\n[C](c.md)\n[D](d.md)"
        result = _extract_inline_links_with_lines(text)
        assert len(result) == 2
        assert result[0][0] == "c.md"
        assert result[1][0] == "d.md"

    def test_inline_code_replaced_correctly_preserves_real_link(self) -> None:
        """Kill lambda→None mutant: inline code must be space-replaced, not None."""
        text = "Use `code_here` then [Link](real.md) end."
        result = _extract_inline_links_with_lines(text)
        assert len(result) == 1
        assert result[0][0] == "real.md"

    def test_inline_code_hiding_link_preserves_adjacent_link(self) -> None:
        """Inline code containing a fake link must not break real link extraction."""
        text = "`[fake](fake.md)` and [real](real.md)"
        result = _extract_inline_links_with_lines(text)
        assert len(result) == 1
        assert result[0][0] == "real.md"

    def test_long_inline_code_does_not_overflow(self) -> None:
        """Kill XX-multiply mutant: space replacement must match exact length."""
        long_code = "`" + "x" * 100 + "`"
        text = f"{long_code} [Link](page.md)"
        result = _extract_inline_links_with_lines(text)
        assert len(result) == 1
        assert result[0][0] == "page.md"


# ─── Mutant-Killing Tests: AdaptiveRuleEngine.run ──────────────────────────


class TestAdaptiveRuleEngineRunMutantKill:
    """Kill mutants in AdaptiveRuleEngine.run with exact assertions."""

    def test_run_propagates_file_path_to_findings(self) -> None:
        """Kills file_path=None mutant in run()."""
        custom_file = Path("docs/specific.md")
        rule = CustomRule(id="ZZ-T", pattern=r"X", message="x", severity="error")
        engine = AdaptiveRuleEngine([rule])
        findings = engine.run(custom_file, "X here")
        assert len(findings) == 1
        assert findings[0].file_path == custom_file

    def test_run_exception_finding_exact_fields(self) -> None:
        """Assert exact fields of error finding — kills string/field mutations."""
        engine = AdaptiveRuleEngine([_BrokenRule()])
        findings = engine.run(_FILE, "text")
        assert len(findings) == 1
        f = findings[0]
        assert f.file_path == _FILE
        assert f.line_no == 0
        assert f.rule_id == "Z901"
        assert f.severity == "error"
        assert "ZZ-BROKEN" in f.message
        assert "RuntimeError" in f.message

    def test_run_exception_does_not_stop_other_rules(self) -> None:
        """A broken rule must not prevent subsequent rules from running."""
        good = CustomRule(id="ZZ-GOOD", pattern=r"a", message="a", severity="info")
        engine = AdaptiveRuleEngine([_BrokenRule(), good])
        findings = engine.run(_FILE, "a text\n")
        rule_ids = [f.rule_id for f in findings]
        assert "Z901" in rule_ids
        assert "ZZ-GOOD" in rule_ids

    def test_run_multiple_rules_all_produce_findings(self) -> None:
        """All rules must run — kills continue→break mutations in the loop."""
        r1 = CustomRule(id="R1", pattern=r"AAA", message="a", severity="error")
        r2 = CustomRule(id="R2", pattern=r"BBB", message="b", severity="error")
        r3 = CustomRule(id="R3", pattern=r"CCC", message="c", severity="error")
        engine = AdaptiveRuleEngine([r1, r2, r3])
        findings = engine.run(_FILE, "AAA BBB CCC")
        assert len(findings) == 3
        assert {f.rule_id for f in findings} == {"R1", "R2", "R3"}


# ─── Mutant-Killing Tests: AdaptiveRuleEngine.run_vsm ──────────────────────


class TestAdaptiveRuleEngineRunVsmMutantKill:
    """Kill mutants in AdaptiveRuleEngine.run_vsm with exact assertions."""

    def test_run_vsm_propagates_file_path(self) -> None:
        """Kills file_path=None mutant in run_vsm()."""
        custom_file = Path("docs/vsm-test.md")
        engine = AdaptiveRuleEngine([VSMBrokenLinkRule()])
        findings = engine.run_vsm(custom_file, "[Bad](ghost.md)", {}, {})
        assert len(findings) == 1
        assert findings[0].file_path == custom_file

    def test_run_vsm_converts_violation_fields(self) -> None:
        """Assert that Violation→RuleFinding conversion preserves all fields."""
        engine = AdaptiveRuleEngine([VSMBrokenLinkRule()])
        findings = engine.run_vsm(_FILE, "[Bad](ghost.md)", {}, {})
        assert len(findings) == 1
        f = findings[0]
        assert isinstance(f, RuleFinding)
        assert f.file_path == _FILE
        assert f.line_no == 1
        assert f.rule_id == "Z101"
        assert f.severity == "error"
        assert "ghost.md" in f.message

    def test_run_vsm_exception_finding_exact_fields(self) -> None:
        """Assert exact fields of error finding from check_vsm exception."""
        engine = AdaptiveRuleEngine([_BrokenVsmRule()])
        findings = engine.run_vsm(_FILE, "text", {}, {})
        assert len(findings) == 1
        f = findings[0]
        assert f.file_path == _FILE
        assert f.line_no == 0
        assert f.rule_id == "Z901"
        assert f.severity == "error"
        assert "ZZ-BROKEN-VSM" in f.message
        assert "check_vsm" in f.message
        assert "RuntimeError" in f.message

    def test_run_vsm_exception_does_not_stop_other_rules(self) -> None:
        """A broken VSM rule must not prevent subsequent rules from running."""
        engine = AdaptiveRuleEngine([_BrokenVsmRule(), VSMBrokenLinkRule()])
        vsm = _make_vsm("/ok/")
        findings = engine.run_vsm(_FILE, "[OK](ok/index.md)", vsm, {})
        # Should have the error finding from _BrokenVsmRule, and 0 from valid link
        error_findings = [f for f in findings if f.rule_id == "Z901"]
        assert len(error_findings) == 1

    def test_run_vsm_multiple_rules_all_produce_findings(self) -> None:
        """Multiple VSM rules must all run — no early break."""
        engine = AdaptiveRuleEngine([VSMBrokenLinkRule(), VSMBrokenLinkRule()])
        findings = engine.run_vsm(_FILE, "[Bad](ghost.md)", {}, {})
        # Both instances should report the broken link
        assert len(findings) == 2
        assert all(f.rule_id == "Z101" for f in findings)

    def test_run_vsm_worker_returns_empty_list(self) -> None:
        """Rule returning no violations is fine — no crash."""
        engine = AdaptiveRuleEngine([VSMBrokenLinkRule()])
        vsm = _make_vsm("/page/")
        findings = engine.run_vsm(_FILE, "[OK](page.md)", vsm, {})
        assert findings == []


# ─── Mutant-Killing Tests: _assert_pickleable ──────────────────────────────


class TestAssertPickleableMutantKill:
    """Kill string-mutation mutants in _assert_pickleable."""

    def test_error_message_mentions_rule_class(self) -> None:
        """Kills type(rule)→type(None) mutant in error message."""

        class _LocalBad(BaseRule):
            @property
            def rule_id(self) -> str:
                return "ZZ-PICKLE"

            def check(self, file_path, text):
                return []

        with pytest.raises(PluginContractError, match="_LocalBad"):
            AdaptiveRuleEngine([_LocalBad()])

    def test_error_message_mentions_rule_id(self) -> None:
        """Kills rule.rule_id mutation in error message."""

        class _LocalBad2(BaseRule):
            @property
            def rule_id(self) -> str:
                return "ZZ-UNIQUEID"

            def check(self, file_path, text):
                return []

        with pytest.raises(PluginContractError, match="ZZ-UNIQUEID"):
            AdaptiveRuleEngine([_LocalBad2()])


# ─── Mutant-Killing Tests: PluginRegistry ──────────────────────────────────


class TestPluginRegistryMutantKill:
    """Kill mutants in PluginRegistry with isolated unit tests."""

    def test_default_group_is_zenzic_rules(self) -> None:
        """Kills __init__ default mutant 'zenzic.rules' → 'XXzenzic.rulesXX'."""
        reg = PluginRegistry()
        assert reg._group == "zenzic.rules"

    def test_custom_group_preserved(self) -> None:
        reg = PluginRegistry(group="my.custom.group")
        assert reg._group == "my.custom.group"

    def test_entry_points_returns_sorted_list(self) -> None:
        """Kills _entry_points key=None mutant (sort by ep.name)."""
        reg = PluginRegistry()
        eps = reg._entry_points()
        names = [ep.name for ep in eps]
        assert names == sorted(names)

    def test_list_rules_always_includes_broken_links(self) -> None:
        """Kills 'broken-links'→'XXbroken-linksXX' mutant in list_rules fallback."""
        reg = PluginRegistry()
        rules = reg.list_rules()
        sources = [r.source for r in rules]
        assert "broken-links" in sources

    def test_list_rules_broken_links_has_z101_id(self) -> None:
        bl = next(r for r in PluginRegistry().list_rules() if r.source == "broken-links")
        assert bl.rule_id == "Z101"
        assert bl.origin == "zenzic"

    def test_list_rules_results_are_sorted_by_source(self) -> None:
        rules = PluginRegistry().list_rules()
        sources = [r.source for r in rules]
        assert sources == sorted(sources)

    def test_list_rules_class_name_is_qualified(self) -> None:
        """Kills class_name formatting mutants."""
        rules = PluginRegistry().list_rules()
        bl = next(r for r in rules if r.source == "broken-links")
        assert "VSMBrokenLinkRule" in bl.class_name
        assert "." in bl.class_name

    def test_load_core_rules_includes_z101(self) -> None:
        """Kills Z101→z101 mutant and not-any→any inversion."""
        reg = PluginRegistry()
        rules = reg.load_core_rules()
        assert any(r.rule_id == "Z101" for r in rules)

    def test_load_core_rules_fallback_is_vsm_broken_link_rule(self) -> None:
        """When no entry points provide Z101, the fallback must be a real VSMBrokenLinkRule."""
        reg = PluginRegistry()
        rules = reg.load_core_rules()
        vsm_rules = [r for r in rules if isinstance(r, VSMBrokenLinkRule)]
        assert len(vsm_rules) >= 1

    def test_load_selected_rules_broken_links_fallback(self) -> None:
        """'broken-links' is loaded even without an entry point."""
        reg = PluginRegistry()
        rules = reg.load_selected_rules(["broken-links"])
        assert len(rules) == 1
        assert isinstance(rules[0], VSMBrokenLinkRule)
        assert rules[0].rule_id == "Z101"

    def test_load_selected_rules_empty_input_returns_empty(self) -> None:
        reg = PluginRegistry()
        assert reg.load_selected_rules([]) == []

    def test_load_selected_rules_whitespace_stripped(self) -> None:
        reg = PluginRegistry()
        rules = reg.load_selected_rules(["  broken-links  "])
        assert len(rules) == 1
        assert isinstance(rules[0], VSMBrokenLinkRule)

    def test_load_selected_rules_blank_entries_skipped(self) -> None:
        reg = PluginRegistry()
        rules = reg.load_selected_rules(["", "  ", "broken-links"])
        assert len(rules) == 1

    def test_load_selected_rules_missing_plugin_raises(self) -> None:
        reg = PluginRegistry()
        with pytest.raises(PluginContractError, match="not found"):
            reg.load_selected_rules(["nonexistent-plugin"])

    def test_load_selected_rules_dedup_preserves_order(self) -> None:
        """Duplicate IDs are loaded once — kills dedup logic mutations."""
        reg = PluginRegistry()
        rules = reg.load_selected_rules(["broken-links", "broken-links", "broken-links"])
        assert len(rules) == 1

    def test_list_rules_skips_non_baserule_entry_point(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Entry point that doesn't produce a BaseRule is skipped."""

        class _FakeEP:
            name = "fake-rule"

            class dist:
                name = "zenzic"

            @staticmethod
            def load():
                return str  # str() is not a BaseRule

        reg = PluginRegistry()
        monkeypatch.setattr(reg, "_entry_points", lambda: [_FakeEP()])
        rules = reg.list_rules()
        # Should still have broken-links fallback
        assert any(r.source == "broken-links" for r in rules)
        # Should NOT have a rule from fake-rule (str is not a BaseRule)
        assert not any(r.source == "fake-rule" for r in rules)

    def test_list_rules_skips_unloadable_entry_point(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Entry point that raises on load() is skipped gracefully."""

        class _FailEP:
            name = "fail-rule"

            class dist:
                name = "zenzic"

            @staticmethod
            def load():
                raise ImportError("module not found")

        reg = PluginRegistry()
        monkeypatch.setattr(reg, "_entry_points", lambda: [_FailEP()])
        rules = reg.list_rules()
        assert any(r.source == "broken-links" for r in rules)
        assert not any(r.source == "fail-rule" for r in rules)

    def test_list_rules_dist_name_fallback_to_zenzic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When ep.dist is None, origin defaults to 'zenzic'."""

        class _NullDistEP:
            name = "null-dist"
            dist = None

            @staticmethod
            def load():
                return VSMBrokenLinkRule

        reg = PluginRegistry()
        monkeypatch.setattr(reg, "_entry_points", lambda: [_NullDistEP()])
        rules = reg.list_rules()
        null_rule = next((r for r in rules if r.source == "null-dist"), None)
        assert null_rule is not None
        assert null_rule.origin == "zenzic"

    def test_load_core_rules_filters_by_dist_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only entry points from the 'zenzic' distribution are loaded as core."""

        class _ExternalEP:
            name = "ext-rule"

            class dist:
                name = "external-package"

            @staticmethod
            def load():
                return _PluginTodoRule

        class _CoreEP:
            name = "core-rule"

            class dist:
                name = "zenzic"

            @staticmethod
            def load():
                return VSMBrokenLinkRule

        reg = PluginRegistry()
        monkeypatch.setattr(reg, "_entry_points", lambda: [_CoreEP(), _ExternalEP()])
        rules = reg.load_core_rules()
        # core-rule should be loaded, ext-rule should not
        rule_ids = [r.rule_id for r in rules]
        assert "Z101" in rule_ids
        assert "PLUG-TODO" not in rule_ids

    def test_load_core_rules_with_z101_already_loaded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When Z101 is already provided by an entry point, no duplicate fallback.
        Kills not-any→any inversion mutant."""

        class _Z101EP:
            name = "broken-links"

            class dist:
                name = "zenzic"

            @staticmethod
            def load():
                return VSMBrokenLinkRule

        reg = PluginRegistry()
        monkeypatch.setattr(reg, "_entry_points", lambda: [_Z101EP()])
        rules = reg.load_core_rules()
        z101_count = sum(1 for r in rules if r.rule_id == "Z101")
        # Exactly 1 — no duplicate from fallback
        assert z101_count == 1

    def test_load_core_rules_fallback_not_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fallback appends a real VSMBrokenLinkRule, not None.
        Kills loaded.append(None) mutant."""
        reg = PluginRegistry()
        monkeypatch.setattr(reg, "_entry_points", lambda: [])
        rules = reg.load_core_rules()
        assert len(rules) == 1
        assert rules[0] is not None
        assert isinstance(rules[0], VSMBrokenLinkRule)
        assert rules[0].rule_id == "Z101"

    def test_load_selected_rules_broken_links_plus_others(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """broken-links fallback + real plugins: both loaded together.
        Kills requested=None and *self.load_selected_rules(None) mutants."""

        class _EP:
            name = "custom-rule"

            class dist:
                name = "zenzic"

            @staticmethod
            def load():
                return _PluginTodoRule

        reg = PluginRegistry()
        monkeypatch.setattr(reg, "_entry_points", lambda: [_EP()])
        rules = reg.load_selected_rules(["broken-links", "custom-rule"])
        assert len(rules) == 2
        assert isinstance(rules[0], VSMBrokenLinkRule)
        assert isinstance(rules[1], _PluginTodoRule)

    def test_load_selected_rules_broken_links_case_sensitive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """'broken-links' check must be exact (case-sensitive).
        Kills 'BROKEN-LINKS' mutant."""
        reg = PluginRegistry()
        # No entry points — broken-links uses fallback
        monkeypatch.setattr(reg, "_entry_points", lambda: [])
        rules = reg.load_selected_rules(["broken-links"])
        assert len(rules) == 1
        assert isinstance(rules[0], VSMBrokenLinkRule)

    def test_list_rules_multiple_plugins_all_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """All plugins in entry points are discovered — kills continue→break.
        Tests that the loop doesn't stop at the first plugin."""

        class _EP1:
            name = "rule-alpha"

            class dist:
                name = "zenzic"

            @staticmethod
            def load():
                return _PluginTodoRule

        class _EP2:
            name = "rule-beta"

            class dist:
                name = "zenzic"

            @staticmethod
            def load():
                return VSMBrokenLinkRule

        reg = PluginRegistry()
        monkeypatch.setattr(reg, "_entry_points", lambda: [_EP1(), _EP2()])
        rules = reg.list_rules()
        sources = [r.source for r in rules]
        assert "rule-alpha" in sources
        assert "rule-beta" in sources

    def test_list_rules_origin_from_dist_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """origin field must come from ep.dist.name — kills string mutations."""

        class _EP:
            name = "my-rule"

            class dist:
                name = "my-package"

            @staticmethod
            def load():
                return VSMBrokenLinkRule

        reg = PluginRegistry()
        monkeypatch.setattr(reg, "_entry_points", lambda: [_EP()])
        rules = reg.list_rules()
        my_rule = next(r for r in rules if r.source == "my-rule")
        assert my_rule.origin == "my-package"


# ─── Mutant-Killing Tests: VSMBrokenLinkRule._to_canonical_url ───────────────


class TestToCanonicalUrlMutantKill:
    """Kill mutants in VSMBrokenLinkRule._to_canonical_url.

    Tested directly on the method to avoid routing through check_vsm overhead.
    """

    _RULE = VSMBrokenLinkRule()

    def _url(
        self,
        href: str,
        source_dir: Path | None = None,
        docs_root: Path | None = None,
        use_directory_urls: bool = True,
    ) -> str | None:
        return self._RULE._to_canonical_url(
            href,
            source_dir,
            docs_root,
            use_directory_urls=use_directory_urls,
        )

    # ── rstrip("/") kills ────────────────────────────────────────────────────

    def test_extensionless_static_asset_no_trailing_slash(self) -> None:
        """Extensionless files like LICENSE must resolve without trailing slash."""
        assert self._url("LICENSE") == "/LICENSE"

    def test_trailing_slash_is_stripped_before_processing(self) -> None:
        """rstrip(None) / lstrip("/") / rstrip("XX/XX") mutants leave a trailing slash
        that would produce "//guide//" or cause wrong path splits."""
        # "guide/" → must become "/guide/"  (rstrip strips the trailing slash)
        result = self._url("guide/")
        assert result == "/guide/"

    def test_trailing_slash_on_md_link(self) -> None:
        """guide.md/ (pathological) — rstrip removes trailing slash first."""
        result = self._url("guide.md/")
        assert result == "/guide/"

    # ── replace("\\", "/") kills ─────────────────────────────────────────────

    def test_backslash_normalized_to_forward_slash(self) -> None:
        """Windows-style backslash must be converted to '/' before URL parsing.
        Kills replace("XX\\XX", "/") and replace("\\", "XX/XX") mutants."""
        result = self._url("a\\b")
        assert result == "/a/b/"

    # ── empty path → None kills ───────────────────────────────────────────────

    def test_empty_path_returns_none(self) -> None:
        """Bare query string has no path — must return None."""
        assert self._url("?foo=bar") is None

    def test_fragment_only_returns_none(self) -> None:
        """Fragment-only href has no path component."""
        assert self._url("#section") is None

    # ── index stripping kills (parts[:-1] → parts[:+1]) ──────────────────────

    def test_index_md_becomes_parent_dir(self) -> None:
        """'dir/index.md' → '/dir/' — kills parts[:-1] → parts[:+1] mutant."""
        result = self._url("dir/index.md")
        assert result == "/dir/"

    def test_bare_index_md_becomes_root(self) -> None:
        """'index.md' → '/' — kills the return '/' after index removal."""
        result = self._url("index.md")
        assert result == "/"

    def test_empty_path_after_md_strip_becomes_root(self) -> None:
        """'index.md' strips to 'index', then index is removed → '/' from empty parts.
        Kills return 'XX/XX' mutant in both empty-parts return statements."""
        result = self._url("index.md")
        assert result == "/"

    def test_nested_index_removed(self) -> None:
        """'a/b/index.md' → '/a/b/' — kills parts[:-1] → parts[:+1] mutant."""
        result = self._url("a/b/index.md")
        assert result == "/a/b/"

    def test_static_asset_path_keeps_exact_suffix_without_trailing_slash(self) -> None:
        """Static assets are file routes and must not be canonicalized as directory URLs."""
        result = self._url("assets/logo.png")
        assert result == "/assets/logo.png"

    def test_html_path_still_normalizes_to_directory_route(self) -> None:
        """HTML page links should normalize to the same canonical route as .md pages."""
        result = self._url("guide/install.html")
        assert result == "/guide/install/"

    def test_asset_with_query_and_fragment_keeps_file_route(self) -> None:
        """Query strings and fragments must not break asset suffix detection."""
        result = self._url("assets/image.webp?v=1#hero")
        assert result == "/assets/image.webp"

    def test_html_path_preserves_extension_when_directory_urls_disabled(self) -> None:
        """Flat URL mode must keep .html extension and avoid trailing slash."""
        result = self._url("guide/install.html", use_directory_urls=False)
        assert result == "/guide/install.html"

    # ── source_dir / docs_root logic kills ───────────────────────────────────

    def test_dotdot_with_context_resolves_correctly(self, tmp_path: Path) -> None:
        """With context, '../sibling.md' resolves relative to source_dir.
        Kills 'and … or' logic mutations in the context guard."""
        docs_root = tmp_path / "docs"
        source_dir = docs_root / "guide"
        # '../sibling' → docs_root/sibling → '/sibling/'
        result = self._url("../sibling.md", source_dir=source_dir, docs_root=docs_root)
        assert result == "/sibling/"

    def test_dotdot_without_context_treated_as_literal(self) -> None:
        """Without source_dir+docs_root, '..' in path is kept as-is (root-relative path)."""
        # No source_dir/docs_root supplied → context branch not taken
        result = self._url("../page.md")
        # '../page.md' → path = '../page' → parts = ['..', 'page'] → '/../page/'
        # This is an awkward URL but the function is pure — no filesystem checks
        assert result is not None  # does not raise, returns some value

    def test_dotdot_escaping_docs_root_returns_none(self, tmp_path: Path) -> None:
        """Path escaping docs_root must return None — kills inversion mutant."""
        docs_root = tmp_path / "docs"
        source_dir = docs_root / "sub"
        # '../../evil' escapes docs_root
        result = self._url("../../evil.md", source_dir=source_dir, docs_root=docs_root)
        assert result is None

    def test_source_dir_none_skips_context_branch(self, tmp_path: Path) -> None:
        """source_dir=None → context branch NOT taken even if docs_root is set.
        Kills 'source_dir is not None or docs_root is not None' mutant."""
        docs_root = tmp_path / "docs"
        # No source_dir → no context-aware resolution regardless of docs_root
        result = self._url("../page.md", source_dir=None, docs_root=docs_root)
        # Without context, '..' is kept literally — no escaping check
        assert result is not None  # does not return None from the context guard

    def test_docs_root_none_skips_context_branch(self, tmp_path: Path) -> None:
        """docs_root=None → context branch NOT taken even if source_dir is set.
        Kills 'source_dir is not None or docs_root is not None' mutant."""
        source_dir = tmp_path / "docs" / "sub"
        result = self._url("../page.md", source_dir=source_dir, docs_root=None)
        assert result is not None  # no context-guard None

    def test_rel_dot_becomes_empty_path(self, tmp_path: Path) -> None:
        """When normpath gives '.' (same-dir reference) path becomes '' → '/'.
        Kills rel != 'XX.XX' and else 'XXXX' mutants."""
        docs_root = tmp_path / "docs"
        source_dir = docs_root / "sub"
        # './sub' relative to source_dir (docs/sub) → normpath → docs/sub → rel='sub'
        # Let's use '.' to get rel='.'
        # source_dir/../ = docs_root itself
        result = self._url("../sub/../", source_dir=source_dir, docs_root=docs_root)
        # This resolves to docs_root itself → rel='.' → path='' → return '/'
        assert result == "/"


# ─── CircularAnchorRule (Z107) ────────────────────────────────────────────────


_ANCHOR_FILE = Path("docs/guide.md")


class TestCircularAnchorRule:
    """18-test suite for built-in Z107, Z505, Z601 rules (D091)."""

    def _rule(self) -> CircularAnchorRule:
        return CircularAnchorRule()

    def test_z107_matches_simple_anchor(self) -> None:
        """[Foo](#foo) → slug('Foo') == 'foo' → Z107."""
        rule = self._rule()
        findings = rule.check(_ANCHOR_FILE, "[Foo](#foo)\n")
        assert len(findings) == 1
        assert findings[0].rule_id == "Z107"
        assert findings[0].line_no == 1
        # "error" per codes.py's CODE_DEFINITIONS (the SSoT) -- this used to
        # assert "warning", locking in a hardcoded-severity bug (fixed in
        # V031_RULES_PY_STRUCTURAL_FIX_AND_STRICT_FLAG_GAP).
        assert findings[0].severity == "error"

    def test_z107_matches_multi_word_anchor(self) -> None:
        """[Foo Bar](#foo-bar) → slug('Foo Bar') == 'foo-bar' → Z107."""
        rule = self._rule()
        findings = rule.check(_ANCHOR_FILE, "[Foo Bar](#foo-bar)\n")
        assert len(findings) == 1
        assert findings[0].rule_id == "Z107"

    def test_z107_no_match_different_target(self) -> None:
        """[Docs](#introduction) — slug('Docs')='docs' != 'introduction' → no finding."""
        rule = self._rule()
        findings = rule.check(_ANCHOR_FILE, "[Docs](#introduction)\n")
        assert findings == []

    def test_z107_ignores_cross_file_link(self) -> None:
        """[text](other.md#foo) is a cross-file link, not a same-page anchor → no finding."""
        rule = self._rule()
        findings = rule.check(_ANCHOR_FILE, "[text](other.md#foo)\n")
        assert findings == []

    def test_z107_ignores_external_url(self) -> None:
        """External URLs are never flagged by Z107."""
        rule = self._rule()
        findings = rule.check(_ANCHOR_FILE, "[Zenzic](https://zenzic.dev)\n")
        assert findings == []

    def test_z107_col_start_correct(self) -> None:
        """col_start points to the opening '[' of the anchor link."""
        rule = self._rule()
        text = "See [Foo](#foo) for details.\n"
        findings = rule.check(_ANCHOR_FILE, text)
        assert len(findings) == 1
        assert findings[0].col_start == text.index("[Foo]")

    def test_z107_true_self_reference_still_flagged(self) -> None:
        """Link text/fragment match AND the link sits under that very heading
        → genuine no-op self-reference → still flagged."""
        rule = self._rule()
        text = "## Foo\n\nSee [Foo](#foo) above.\n"
        findings = rule.check(_ANCHOR_FILE, text)
        assert len(findings) == 1
        assert findings[0].rule_id == "Z107"

    def test_z107_no_false_positive_cross_section_reference(self) -> None:
        """[Z101](#z101) written from inside a *different* section (## Z104)
        must NOT be flagged: it navigates to a distinct section that merely
        shares a name with its own link text, not a circular no-op."""
        rule = self._rule()
        text = "## Z104\n\nSee also [Z101](#z101) for the related code.\n\n## Z101\n\nDetails.\n"
        findings = rule.check(_ANCHOR_FILE, text)
        assert findings == []


# ─── UntaggedCodeBlockRule (Z505) ─────────────────────────────────────────────


class TestUntaggedCodeBlockRule:
    def _rule(self) -> UntaggedCodeBlockRule:
        return UntaggedCodeBlockRule()

    def test_z505_untagged_fence_detected(self) -> None:
        """Opening ``` with no language tag → one Z505 finding."""
        rule = self._rule()
        text = "```\nsome code\n```\n"
        findings = rule.check(_ANCHOR_FILE, text)
        assert len(findings) == 1
        assert findings[0].rule_id == "Z505"
        assert findings[0].line_no == 1
        assert findings[0].severity == "warning"

    def test_z505_tagged_fence_no_finding(self) -> None:
        """Opening ```python has a tag → no finding."""
        rule = self._rule()
        text = "```python\nx = 1\n```\n"
        findings = rule.check(_ANCHOR_FILE, text)
        assert findings == []

    def test_z505_closing_fence_not_flagged(self) -> None:
        """Closing ``` of a tagged block is never flagged."""
        rule = self._rule()
        text = "```toml\nkey = 'val'\n```\n"
        findings = rule.check(_ANCHOR_FILE, text)
        assert findings == []

    def test_z505_tilde_fence_untagged(self) -> None:
        """~~~ without a language tag → Z505 (tilde fences supported)."""
        rule = self._rule()
        text = "~~~\ncode\n~~~\n"
        findings = rule.check(_ANCHOR_FILE, text)
        assert len(findings) == 1
        assert findings[0].rule_id == "Z505"

    def test_z505_multiple_untagged_blocks(self) -> None:
        """Two untagged fences in the same file → two Z505 findings."""
        rule = self._rule()
        text = "```\nblock1\n```\nText.\n```\nblock2\n```\n"
        findings = rule.check(_ANCHOR_FILE, text)
        assert len(findings) == 2

    def test_z505_content_inside_not_flagged(self) -> None:
        """Lines inside a fence block are not inspected for the fence pattern."""
        rule = self._rule()
        # Inner ``` looks like a fence but is inside the block → ignored
        text = "```markdown\n```\ninner content\n```\n```\n"
        findings = rule.check(_ANCHOR_FILE, text)
        # CEO-140: ``` closes the markdown block (no info string, same char, same
        # length). Then the third ``` re-opens an untagged block → Z505.
        # Structure: open(md) → close → open(untagged) → close
        # So: 0 from tagged, 1 from second untagged open
        assert len(findings) == 1

    def test_z505_info_string_with_title_not_flagged(self) -> None:
        """```python title="test.py" has a language tag → no finding (CEO-138)."""
        rule = self._rule()
        text = '```python title="test.py"\nx = 1\n```\n'
        findings = rule.check(_ANCHOR_FILE, text)
        assert findings == []

    def test_z505_info_string_with_metadata_not_flagged(self) -> None:
        """```bash showLineNumbers {1-3} has a language tag → no finding (CEO-138)."""
        rule = self._rule()
        text = "```bash showLineNumbers {1-3}\necho hi\n```\n"
        findings = rule.check(_ANCHOR_FILE, text)
        assert findings == []

    def test_z505_closing_fence_with_info_does_not_close(self) -> None:
        """A closing fence with info string is an opener, not a closer (CEO-140)."""
        rule = self._rule()
        # ````text opens, ```mermaid does NOT close (has info), ``` closes.
        text = "````text\n```mermaid\nflowchart\n```\n````\n"
        findings = rule.check(_ANCHOR_FILE, text)
        # ````text is tagged → no Z505
        assert findings == []


# ─── BrandObsolescenceRule (Z601) ─────────────────────────────────────────────


def _meta(
    obsolete: list[str] | None = None,
    release: str = "NextRelease",
    exclude: list[str] | None = None,
) -> ProjectMetadata:
    kwargs: dict = {"release_name": release, "obsolete_names": obsolete or []}  # type: ignore[type-arg]
    if exclude is not None:
        kwargs["obsolete_names_exclude_patterns"] = exclude
    return ProjectMetadata(**kwargs)


class TestBrandObsolescenceRule:
    def _rule(self, meta: ProjectMetadata) -> BrandObsolescenceRule:
        return BrandObsolescenceRule(meta)

    def test_z601_empty_obsolete_no_findings(self) -> None:
        """When obsolete_names is empty, rule always returns []."""
        rule = self._rule(_meta(obsolete=[]))
        findings = rule.check(_ANCHOR_FILE, "OldBrand was the old name.\n")
        assert findings == []

    def test_z601_match_emits_warning(self) -> None:
        """Obsolete term found → one Z601 warning with remediation hint."""
        rule = self._rule(_meta(obsolete=["OldBrand"]))
        findings = rule.check(_ANCHOR_FILE, "OldBrand is documented here.\n")
        assert len(findings) == 1
        assert findings[0].rule_id == "Z601"
        assert findings[0].severity == "warning"
        assert "OldBrand" in findings[0].message
        assert "semantic versioning" in findings[0].message

    def test_z601_suppress_md_html_comment(self) -> None:
        """CEO-143: HTML comment suppression (Markdown .md syntax)."""
        rule = self._rule(_meta(obsolete=["OldBrand"]))
        text = "OldBrand was the old name. <!-- zenzic:ignore: Z601 -->\n"
        findings = rule.check(_ANCHOR_FILE, text)
        assert findings == []

    def test_z601_suppress_mdx_jsx_comment(self) -> None:
        """CEO-143: JSX comment suppression (MDX .mdx syntax)."""
        rule = self._rule(_meta(obsolete=["OldBrand"]))
        mdx_file = Path("docs/guide/history.mdx")
        text = "The OldBrand era defined our foundations. {/* zenzic:ignore: Z601 */}\n"
        findings = rule.check(mdx_file, text)
        assert findings == []

    def test_z601_suppress_only_correct_code(self) -> None:
        """CEO-143: A suppression comment for a different code does NOT suppress Z601."""
        rule = self._rule(_meta(obsolete=["OldBrand"]))
        text = "OldBrand was the old name. <!-- zenzic:ignore: Z107 -->\n"
        findings = rule.check(_ANCHOR_FILE, text)
        assert len(findings) == 1
        assert findings[0].rule_id == "Z601"

    def test_z601_historical_tag_no_longer_suppresses(self) -> None:
        """CEO-143: The deprecated [HISTORICAL] token is no longer a suppression mechanism."""
        rule = self._rule(_meta(obsolete=["OldBrand"]))
        text = "OldBrand was the old name. [HISTORICAL]\n"
        findings = rule.check(_ANCHOR_FILE, text)
        # [HISTORICAL] is plain text — does not suppress Z601
        assert len(findings) == 1
        assert findings[0].rule_id == "Z601"

    def test_z601_path_in_exclude_patterns_skipped(self) -> None:
        """File matching an exclusion glob is skipped entirely."""
        rule = self._rule(_meta(obsolete=["OldBrand"], exclude=["CHANGELOG*.md"]))
        cl_file = Path("CHANGELOG.md")
        findings = rule.check(cl_file, "OldBrand was the old name.\n")
        assert findings == []

    def test_z601_case_insensitive(self) -> None:
        """Z601 is case-insensitive: 'oldbrand' also triggers when lowercased."""
        rule = self._rule(_meta(obsolete=["OldBrand"]))
        findings = rule.check(_ANCHOR_FILE, "oldbrand is no longer used.\n")
        assert len(findings) == 1
        assert findings[0].match_text.lower() == "oldbrand"

    def test_z601_multiple_names_multiple_findings(self) -> None:
        """Each unique obsolete term on a line → its own finding."""
        rule = self._rule(_meta(obsolete=["OldBrand", "LegacyTerm"]))
        text = "OldBrand and LegacyTerm are both deprecated.\n"
        findings = rule.check(_ANCHOR_FILE, text)
        assert len(findings) == 2
        codes = {f.rule_id for f in findings}
        assert codes == {"Z601"}


# ─── MalformedFrontmatterRule (Z506) ──────────────────────────────────────────


class TestMalformedFrontmatterRule:
    """Suite for Z506 MALFORMED_FRONTMATTER — built-in always-active rule."""

    def _rule(self) -> MalformedFrontmatterRule:
        return MalformedFrontmatterRule()

    def test_double_dash_opening_fires_z506(self, tmp_path: Path) -> None:
        """First line '--' (2 dashes) instead of '---' → Z506."""
        text = "--\ntitle: test\n---\n\nContent here.\n"
        f = tmp_path / "bad.md"
        findings = self._rule().check(f, text)
        assert len(findings) == 1
        assert findings[0].rule_id == "Z506"
        assert findings[0].line_no == 1
        assert findings[0].severity == "error"

    def test_physical_fixture_fires_z506(self) -> None:
        """Reads a physical fixture from disk to assert Z506 fires on line 1."""
        fixture_path = Path(__file__).parent / "fixtures" / "z506_malformed.md"
        text = fixture_path.read_text(encoding="utf-8")
        findings = self._rule().check(fixture_path, text)
        assert len(findings) == 1
        assert findings[0].rule_id == "Z506"
        assert findings[0].line_no == 1

    def test_four_dashes_fires_z506(self, tmp_path: Path) -> None:
        """First line '----' (4 dashes) → Z506."""
        text = "----\ntitle: test\n---\n\nContent.\n"
        f = tmp_path / "bad.md"
        findings = self._rule().check(f, text)
        assert len(findings) == 1
        assert findings[0].rule_id == "Z506"
        assert findings[0].line_no == 1

    def test_trailing_chars_fires_z506(self, tmp_path: Path) -> None:
        """First line '--- trailing stuff' → Z506 (not a clean '---')."""
        text = "--- trailing stuff\ntitle: test\n---\n\nContent.\n"
        f = tmp_path / "bad.md"
        findings = self._rule().check(f, text)
        assert len(findings) == 1
        assert findings[0].rule_id == "Z506"

    def test_valid_frontmatter_no_finding(self, tmp_path: Path) -> None:
        """Correct '---' on line 1 → no Z506."""
        text = "---\ntitle: test\n---\n\nContent here.\n"
        f = tmp_path / "ok.md"
        findings = self._rule().check(f, text)
        assert findings == []

    def test_no_frontmatter_no_finding(self, tmp_path: Path) -> None:
        """File with no frontmatter at all → no Z506."""
        text = "# Heading\n\nContent here.\n"
        f = tmp_path / "ok.md"
        findings = self._rule().check(f, text)
        assert findings == []

    def test_single_dash_no_finding(self, tmp_path: Path) -> None:
        """First line '-' (single dash) is not malformed frontmatter → no Z506."""
        text = "-\ntitle: test\n---\n\nContent.\n"
        f = tmp_path / "ok.md"
        findings = self._rule().check(f, text)
        assert findings == []

    def test_empty_file_no_finding(self, tmp_path: Path) -> None:
        """Empty file → no Z506."""
        f = tmp_path / "empty.md"
        findings = self._rule().check(f, "")
        assert findings == []

    def test_z506_finding_exact_fields(self, tmp_path: Path) -> None:
        """Assert all RuleFinding fields for a Z506 violation."""
        text = "--\ntitle: test\n---\n"
        f = tmp_path / "bad.md"
        findings = self._rule().check(f, text)
        assert len(findings) == 1
        v = findings[0]
        assert v.file_path == f
        assert v.line_no == 1
        assert v.rule_id == "Z506"
        assert v.severity == "error"
        assert v.is_error
        assert "'--'" in v.message
        assert "---" in v.message
        assert v.match_text == "--"
        assert v.col_start == 0

    def test_z506_five_dashes_fires(self, tmp_path: Path) -> None:
        """'-----' also triggers Z506."""
        text = "-----\ntitle: x\n---\n"
        findings = self._rule().check(tmp_path / "f.md", text)
        assert len(findings) == 1
        assert findings[0].rule_id == "Z506"

    def test_z506_only_fires_once_per_file(self, tmp_path: Path) -> None:
        """Z506 fires at most once per file (line 1 only)."""
        text = "--\n--\n--\n"
        findings = self._rule().check(tmp_path / "f.md", text)
        assert len(findings) == 1

    def test_z506_suppression_honored(self, tmp_path: Path) -> None:
        """<!-- zenzic:ignore: Z506 --> on line 1 suppresses the finding."""
        text = "-- <!-- zenzic:ignore: Z506 -->\ntitle: test\n---\n"
        findings = self._rule().check(tmp_path / "ok.md", text)
        assert findings == []

    def test_z506_integrated_in_rule_engine(self, tmp_path: Path) -> None:
        """MalformedFrontmatterRule fires when run through AdaptiveRuleEngine."""
        engine = AdaptiveRuleEngine([MalformedFrontmatterRule()])
        text = "--\ntitle: test\n---\n\nContent.\n"
        findings = engine.run(tmp_path / "bad.md", text)
        assert len(findings) == 1
        assert findings[0].rule_id == "Z506"

    def test_z506_built_in_via_build_rule_engine(self) -> None:
        """Z506 must be in the built-in always-active rule set."""
        from zenzic.core.scanner import _build_rule_engine

        config = ZenzicConfig()
        engine = _build_rule_engine(config)
        assert engine is not None
        rule_ids = {r.rule_id for r in engine._rules}
        assert "Z506" in rule_ids
