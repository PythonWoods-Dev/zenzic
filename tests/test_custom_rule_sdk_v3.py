# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from zenzic.core.rules import RuleFinding
from zenzic.models.config import ZenzicConfig
from zenzic.models.rules import RuleMetadata
from zenzic.sdk import ZenzicRuleV3
from zenzic.sdk.examples import NoTodoRule


class CustomLinkRule(ZenzicRuleV3):
    metadata = RuleMetadata(
        code="ZZ-NO-HTTP",
        title="Insecure HTTP Link",
        description="Links must use HTTPS rather than HTTP.",
        severity="error",
        category="governance",
        penalty=3.0,
    )

    def visit_link(
        self, file_path: Path, line_no: int, link_text: str, target_url: str
    ) -> list[RuleFinding]:
        if target_url.startswith("http://"):
            return [
                self.create_finding(
                    file_path=file_path,
                    line_no=line_no,
                    message=f"Insecure HTTP link found: {target_url}",
                    match_text=target_url,
                )
            ]
        return []


class CustomCodeBlockRule(ZenzicRuleV3):
    metadata = RuleMetadata(
        code="ZZ-NO-BASH",
        title="Bash Code Block Forbidden",
        description="Fenced bash code blocks are not allowed in this project.",
        severity="error",
        category="governance",
        penalty=2.0,
    )

    def visit_code_block(
        self, file_path: Path, start_line: int, lang: str, code: str
    ) -> list[RuleFinding]:
        if lang == "bash":
            return [
                self.create_finding(
                    file_path=file_path,
                    line_no=start_line,
                    message=f"Forbidden bash code block: {code.strip()!r}",
                    match_text=lang,
                )
            ]
        return []


def test_sdk_v3_rule_metadata() -> None:
    rule = NoTodoRule()
    assert rule.rule_id == "ZZ-NO-TODO"
    assert rule.metadata.severity == "warning"
    assert rule.metadata.category == "content"
    assert rule.metadata.penalty == 1.0


def test_sdk_v3_visit_line(tmp_path: Path) -> None:
    rule = NoTodoRule()
    doc_path = tmp_path / "docs" / "index.md"
    content = "# Title\n\nThis is a line with TODO marker.\nAnother clean line."
    findings = rule.check(doc_path, content)
    assert len(findings) == 1
    assert findings[0].rule_id == "ZZ-NO-TODO"
    assert findings[0].line_no == 3
    assert findings[0].severity == "warning"


def test_sdk_v3_visit_link(tmp_path: Path) -> None:
    rule = CustomLinkRule()
    doc_path = tmp_path / "docs" / "guide.md"
    content = "[Good](https://secure.org)\n[Bad](http://insecure.org)"
    findings = rule.check(doc_path, content)
    assert len(findings) == 1
    assert findings[0].rule_id == "ZZ-NO-HTTP"
    assert findings[0].line_no == 2
    assert findings[0].severity == "error"


def test_sdk_v3_visit_code_block(tmp_path: Path) -> None:
    rule = CustomCodeBlockRule()
    doc_path = tmp_path / "docs" / "guide.md"
    content = "# Title\n\n```python\nprint('fine')\n```\n\n```bash\nrm -rf /\n```\n"
    findings = rule.check(doc_path, content)
    assert len(findings) == 1
    assert findings[0].rule_id == "ZZ-NO-BASH"
    assert findings[0].line_no == 7
    assert findings[0].severity == "error"


def test_sdk_v3_loading_via_config(tmp_path: Path) -> None:
    from zenzic.core.scanner import _build_rule_engine
    from zenzic.models.config import CustomRuleConfig

    config = ZenzicConfig(
        custom_rules=[CustomRuleConfig(class_name="zenzic.sdk.examples.NoTodoRule")]
    )

    engine = _build_rule_engine(config)
    doc_path = tmp_path / "docs" / "index.md"
    content = "Line 1\nLine 2 TODO fix this\nLine 3"

    findings = engine.run(doc_path, content)
    todo_findings = [f for f in findings if f.rule_id == "ZZ-NO-TODO"]
    assert len(todo_findings) == 1
    assert todo_findings[0].line_no == 2
