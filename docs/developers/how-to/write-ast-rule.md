---
description: "Write project-local custom analysis rules using the Custom Rule SDK v3 (ZenzicRuleV3 + RuleMetadata)."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Writing Custom Rules (Custom Rule SDK v3)

> **v0.28.0 Breaking Change:** The legacy Custom Rules API v2 (`BaseASTRule`) was **hard deprecated and removed** in Zenzic v0.28.0. All custom rules must use the **Custom Rule SDK v3** (`ZenzicRuleV3` + `RuleMetadata`).

---

## Migration from API v2 to SDK v3

The table below illustrates the structural shift from the un-typed v2 API to the governed, typed SDK v3.

### Before (API v2 — Removed in v0.28.0)

```python
from collections.abc import Generator
from pathlib import Path
from zenzic.core.ast import BlockNode
from zenzic.core.rules import RuleFinding
from zenzic.rules.base import BaseASTRule


class LegacyRule(BaseASTRule):
    def __init__(self) -> None:
        super().__init__(rule_id="LOCAL-001", severity="error")

    def visit_block_node(self, node: BlockNode, file_path: Path) -> Generator[RuleFinding, None, None]:
        ...

    def visit_html_node(self, node: object, file_path: Path) -> Generator[RuleFinding, None, None]:
        ...
```

### After (Custom Rule SDK v3 — Current)

```python
from pathlib import Path
from zenzic.sdk import ZenzicRuleV3, RuleMetadata
from zenzic.core.rules import RuleFinding


class ModernRule(ZenzicRuleV3):
    metadata = RuleMetadata(
        code="ZZ-NO-BAD-URL",
        title="Forbidden Internal URL",
        description="Internal URLs must not appear in published documentation.",
        severity="warning",
        category="content",
        penalty=1.0,
    )

    def visit_line(self, file_path: Path, line_no: int, line_text: str) -> list[RuleFinding]:
        if "bad.example.com" in line_text:
            return [
                self.create_finding(
                    file_path=file_path,
                    line_no=line_no,
                    message="Forbidden internal URL found.",
                    matched_line=line_text,
                )
            ]
        return []
```

---

## Overview

Custom Rule SDK v3 allows developers to author deterministic Python linting rules. Rules placed inside `.zenzic/rules/*.py` are auto-discovered at scan startup. Alternatively, rules can be configured via `[[custom_rules]]` in `.zenzic.toml`:

```toml
[[custom_rules]]
class_name = "my_module.my_rules.ModernRule"
```

SDK v3 rules inherit from `ZenzicRuleV3` and require a typed `RuleMetadata` declaration.

---

## The `RuleMetadata` Schema

`RuleMetadata` dictates finding code, severity, category (for DQS weighting), and penalty impact:

| Attribute | Type | Description | Default |
|---|---|---|---|
| `code` | `str` | Unique rule identifier (e.g. `"ZZ-NO-BAD-URL"` or `"MY_RULE_001"`). | Required |
| `title` | `str` | Short title of the rule. | Required |
| `description` | `str` | Full description of the rule check. | Required |
| `severity` | `"error" \| "warning" \| "info"` | Severity level of produced findings. | `"warning"` |
| `category` | `"structural" \| "navigation" \| "content" \| "brand" \| "governance"` | Taxonomy category for scoring. | `"content"` |
| `penalty` | `float` | DQS penalty cost per finding. | `1.0` |
| `docs_url` | `Optional[str]` | Optional URL to rule documentation. | `None` |
| `supports_autofix` | `bool` | Whether automated quick-fixes are supported. | `False` |

---

## Visitor Interface

SDK v3 rules can override any of the following visitor hooks:

- `visit_document(self, file_path: Path, text: str) -> list[RuleFinding]`: Inspect full raw source.
- `visit_line(self, file_path: Path, line_no: int, line_text: str) -> list[RuleFinding]`: Inspect individual lines.
- `visit_link(self, file_path: Path, line_no: int, link_text: str, target_url: str) -> list[RuleFinding]`: Inspect links.
- `visit_heading(self, file_path: Path, line_no: int, level: int, title: str) -> list[RuleFinding]`: Inspect headings.
- `visit_code_block(self, file_path: Path, start_line: int, lang: str, code: str) -> list[RuleFinding]`: Inspect code blocks.

---

## Deterministic Constraints (ADR-007 Sovereign Sandbox)

To preserve mathematical determinism ($O(N)$ runtime complexity) and maintain engine security, all custom rules MUST adhere to these strict constraints:

1. **Zero Network I/O**: Rules must never make HTTP, HTTPS, DNS, or socket requests.
2. **Zero Subprocesses**: Invoking subprocesses (`subprocess.run`, `os.system`) is strictly forbidden (ADR-002).
3. **No Probabilistic NLP**: Rules must be deterministic mathematical functions. Probabilistic models and external AI/LLM APIs are prohibited.
4. **RE2 Regular Expressions (ADR-013)**: Regular expressions must use linear-time `google-re2` via `import zenzic.core.regex as re` to prevent Catastrophic Backtracking (ReDoS).
5. **Pure Functions**: Rules must not mutate the filesystem, shared global state, or cross-file caches.

---

## Testing SDK v3 Rules

```python
from pathlib import Path
from zenzic.sdk.examples import NoTodoRule

def test_no_todo_rule(tmp_path: Path) -> None:
    rule = NoTodoRule()
    doc_path = tmp_path / "docs" / "index.md"
    findings = rule.check(doc_path, "Line 1\nTODO fix this\nLine 3")
    assert len(findings) == 1
    assert findings[0].rule_id == "ZZ-NO-TODO"
    assert findings[0].line_no == 2
```

---

## See Also

- [Add Custom Lint Rules](../../how-to/add-custom-rules.md)
- [Writing Plugin Rules](./write-plugin.md)
- [Finding Codes](../../reference/finding-codes.md)
