# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for Custom Rules SDK v3 and expanded Auto-Fix functionality (Z121 & Z603)."""

from __future__ import annotations

from pathlib import Path

from zenzic.core.rules import AdaptiveRuleEngine, RuleFinding
from zenzic.core.scanner import _build_rule_engine
from zenzic.models.config import ZenzicConfig
from zenzic.models.rules import RuleMetadata
from zenzic.sdk.rules import ZenzicRuleV3


class DummyCrashingRule(ZenzicRuleV3):
    """A test rule that raises an unexpected Python exception."""

    metadata = RuleMetadata(
        code="CRASH-999",
        title="Crashing Rule",
        description="Crashing rule for testing",
        severity="error",
        category="content",
        penalty=1.0,
    )

    def visit_document(self, file_path: Path, text: str) -> list[RuleFinding]:
        raise ValueError("Simulated crash")


class DummyWorkingRule(ZenzicRuleV3):
    """A normal working custom SDK v3 rule."""

    metadata = RuleMetadata(
        code="WORK-001",
        title="Working Rule",
        description="Working rule for testing",
        severity="warning",
        category="content",
        penalty=1.0,
    )

    def visit_line(self, file_path: Path, line_no: int, line_text: str) -> list[RuleFinding]:
        if "badword" in line_text:
            return [
                self.create_finding(
                    file_path=file_path,
                    line_no=line_no,
                    message="Found badword",
                    matched_line=line_text,
                )
            ]
        return []


def test_custom_rule_crash_handling() -> None:
    """If a rule raises an arbitrary exception, it is caught and converted to Z901."""
    rule = DummyCrashingRule()
    engine = AdaptiveRuleEngine([rule])

    findings = engine.run(Path("dummy.md"), "# Hello")
    assert len(findings) == 1
    assert findings[0].rule_id == "Z901"
    assert "raised an unexpected exception" in findings[0].message
    assert "ValueError" in findings[0].message


def test_custom_rule_working() -> None:
    """A normal custom v3 rule executes and reports findings correctly."""
    rule = DummyWorkingRule()
    engine = AdaptiveRuleEngine([rule])

    findings = engine.run(Path("dummy.md"), "# Heading\nThis line has a badword")
    assert len(findings) == 1
    assert findings[0].rule_id == "WORK-001"
    assert findings[0].line_no == 2
    assert findings[0].message == "Found badword"


def test_custom_rule_file_autodiscovery(tmp_path: Path) -> None:
    """Scanner automatically discovers and registers custom SDK v3 rules from .zenzic/rules/."""
    repo_root = tmp_path / "myrepo"
    repo_root.mkdir()
    (repo_root / "docs").mkdir()

    config_file = repo_root / ".zenzic.toml"
    config_file.write_text("[project]\nname = 'test'\n", encoding="utf-8")

    rules_dir = repo_root / ".zenzic" / "rules"
    rules_dir.mkdir(parents=True)

    rule_py = rules_dir / "my_custom_rule.py"
    rule_py.write_text(
        """
from pathlib import Path
from zenzic.sdk import ZenzicRuleV3, RuleMetadata
from zenzic.core.rules import RuleFinding

class MyAwesomeRule(ZenzicRuleV3):
    metadata = RuleMetadata(
        code="AWESOME-101",
        title="Awesome Rule",
        description="Awesome rule",
        severity="info",
        category="content",
        penalty=0.5,
    )
    def visit_document(self, file_path: Path, text: str) -> list[RuleFinding]:
        return [self.create_finding(file_path=file_path, line_no=1, message="Awesome")]
""",
        encoding="utf-8",
    )

    config, _ = ZenzicConfig.load(repo_root)
    engine = _build_rule_engine(config)
    assert engine is not None

    rule_ids = {r.rule_id for r in engine._rules}
    assert "AWESOME-101" in rule_ids
