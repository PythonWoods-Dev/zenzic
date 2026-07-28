# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for Custom Rules v2 (AST-based) and expanded Auto-Fix functionality (Z121 & Z603)."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from zenzic.core.ast import BlockNode
from zenzic.core.rules import AdaptiveRuleEngine, RuleFinding
from zenzic.core.scanner import _build_rule_engine
from zenzic.core.validator import HtmlNodeInfo
from zenzic.models.config import ZenzicConfig
from zenzic.rules.base import BaseASTRule


class DummyInfiniteLoopRule(BaseASTRule):
    """A test rule that goes into an infinite loop (exceeds budget)."""

    def __init__(self) -> None:
        super().__init__(rule_id="LOOP-999", max_visits=10)

    def visit_block_node(
        self,
        node: BlockNode,
        file_path: Path,
    ) -> Generator[RuleFinding, None, None]:
        # Infinite loop simulation: just keep calling check_budget
        while True:
            self.check_budget()
            yield RuleFinding(
                file_path=file_path,
                line_no=1,
                rule_id=self.rule_id,
                message="Looping",
                severity=self.severity,
            )

    def visit_html_node(
        self,
        node: HtmlNodeInfo,
        file_path: Path,
    ) -> Generator[RuleFinding, None, None]:
        pass


class DummyCrashingRule(BaseASTRule):
    """A test rule that raises an unexpected Python exception."""

    def __init__(self) -> None:
        super().__init__(rule_id="CRASH-999")

    def visit_block_node(
        self,
        node: BlockNode,
        file_path: Path,
    ) -> Generator[RuleFinding, None, None]:
        raise ValueError("Simulated crash")

    def visit_html_node(
        self,
        node: HtmlNodeInfo,
        file_path: Path,
    ) -> Generator[RuleFinding, None, None]:
        pass


class DummyWorkingRule(BaseASTRule):
    """A normal working custom AST rule."""

    def __init__(self) -> None:
        super().__init__(rule_id="WORK-001")

    def visit_block_node(
        self,
        node: BlockNode,
        file_path: Path,
    ) -> Generator[RuleFinding, None, None]:
        yield RuleFinding(
            file_path=file_path,
            line_no=1,
            rule_id=self.rule_id,
            message="Found block node",
            severity=self.severity,
        )

    def visit_html_node(
        self,
        node: HtmlNodeInfo,
        file_path: Path,
    ) -> Generator[RuleFinding, None, None]:
        if node.tag == "a":
            yield RuleFinding(
                file_path=file_path,
                line_no=node.line_no,
                rule_id=self.rule_id,
                message=f"Found html tag a with href {node.href}",
                severity=self.severity,
            )


def test_custom_rule_timeout_handling() -> None:
    """If a rule exceeds max_visits, ZenzicRuleTimeout is raised, caught and converted to Z902."""
    rule = DummyInfiniteLoopRule()
    engine = AdaptiveRuleEngine([rule])

    # Checking a simple markdown file will trigger visit_block_node and exceed budget
    findings = engine.run(Path("dummy.md"), "# Hello")
    assert len(findings) == 1
    assert findings[0].rule_id == "Z902"
    assert "exceeded execution limit" in findings[0].message


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
    """A normal custom rule executes and reports findings correctly."""
    rule = DummyWorkingRule()
    engine = AdaptiveRuleEngine([rule])

    findings = engine.run(Path("dummy.md"), "# Heading\n<a href='https://example.com'>link</a>")
    # We expect 4 findings: 3 from BlockNode (Document, Heading, Paragraph) and 1 from HTML tag a
    assert len(findings) == 4
    assert any(f.message == "Found block node" for f in findings)
    assert any("Found html tag a with href" in f.message for f in findings)


def test_custom_rule_file_autodiscovery(tmp_path: Path) -> None:
    """Scanner automatically discovers and registers custom AST rules from .zenzic/rules/."""
    # Setup temporary docs/repo tree
    repo_root = tmp_path / "myrepo"
    repo_root.mkdir()
    (repo_root / "docs").mkdir()

    # Create config file
    config_file = repo_root / ".zenzic.toml"
    config_file.write_text("[project]\nname = 'test'\n", encoding="utf-8")

    # Create custom rules folder and a dummy custom rule class
    rules_dir = repo_root / ".zenzic" / "rules"
    rules_dir.mkdir(parents=True)

    rule_py = rules_dir / "my_custom_rule.py"
    rule_py.write_text(
        """
from zenzic.rules import RuleFinding
from zenzic.rules.base import BaseASTRule

class MyAwesomeRule(BaseASTRule):
    def __init__(self):
        super().__init__(rule_id="AWESOME-101")
    def visit_block_node(self, node, file_path):
        yield RuleFinding(file_path=file_path, line_no=1, rule_id=self.rule_id, message="Awesome", severity=self.severity)
    def visit_html_node(self, node, file_path):
        pass
""",
        encoding="utf-8",
    )

    config, _ = ZenzicConfig.load(repo_root)
    engine = _build_rule_engine(config)
    assert engine is not None

    # Check if AWESOME-101 is registered
    rule_ids = {r.rule_id for r in engine._rules}
    assert "AWESOME-101" in rule_ids


def test_autofix_z505_z108_z603(tmp_path: Path) -> None:
    """Test autofixes for untagged code blocks (Z505), empty link text (Z108), and dead suppression (Z603)."""
    from zenzic.core.mutator import (
        DeadSuppressionMutation,
        EmptyLinkTextMutation,
        Mutator,
        UntaggedCodeBlockMutation,
    )
    from zenzic.core.parser import parse, serialize

    # 1. Z505 Auto-Fix tests
    z505_input = "```\nprint('hello')\n```\n"
    mutator_z505 = Mutator([UntaggedCodeBlockMutation()])
    ast505 = parse(z505_input)
    new_ast505, changed505 = mutator_z505.mutate(ast505)
    assert changed505
    assert serialize(new_ast505) == "```text\nprint('hello')\n```\n"

    # 2. Z108 Auto-Fix tests
    z108_input = "[](https://example.com)\n"
    mutator_z108 = Mutator([EmptyLinkTextMutation()])
    ast108 = parse(z108_input)
    new_ast108, changed108 = mutator_z108.mutate(ast108)
    assert changed108
    assert serialize(new_ast108) == "[TODO](https://example.com)\n"

    # 2. Z603 Auto-Fix tests (Dead suppression)
    text_with_dead = (
        "Some text <!-- zenzic:ignore: Z101 -->\n"
        "Other line <a href='https://example.com' data-zenzic-ignore>link</a>\n"
    )
    # Both lines 1 and 2 contain dead suppressions
    mutator_z603 = Mutator([DeadSuppressionMutation({1, 2})])
    ast = parse(text_with_dead)
    new_ast, changed = mutator_z603.mutate(ast)
    assert changed
    res = serialize(new_ast)
    # The comment on line 1 should be gone
    assert "zenzic:ignore" not in res
    # The data-zenzic-ignore attribute on line 2 should be gone
    assert "data-zenzic-ignore" not in res
    # But the surrounding text and tag remain intact
    assert "Some text" in res
    assert "<a href='https://example.com'>link</a>" in res
