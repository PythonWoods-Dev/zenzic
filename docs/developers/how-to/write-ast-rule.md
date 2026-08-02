---
description: "Write project-local custom analysis rules using the BaseASTRule API v2. Zero packaging, zero entry-points."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Writing Custom AST Rules (API v2)

> **v0.20.0+** — This guide covers the **drop-in Custom Rules API v2** (`BaseASTRule`).
> For regex-based rules that require no Python, see [Add Custom Lint Rules](../../how-to/add-custom-rules.md).
> For distributable plugin packages (entry-point API v1), see [Writing Plugin Rules](./write-plugin.md).

---

## When to use each API

| Scenario | Recommended API |
|---|---|
| Simple keyword / pattern match | [TOML `[[custom_rules]]`](../../how-to/add-custom-rules.md) |
| Multi-line or structural analysis (no distribution needed) | **Custom AST Rules v2** ← this guide |
| Distributable plugin for other teams / open-source | [Plugin API v1 (`BaseRule`)](./write-plugin.md) |

---

## Overview

Custom AST Rules v2 are single Python files placed inside your repository under
`.zenzic/rules/`. Zenzic auto-discovers them at scan startup — no `pyproject.toml`,
no `plugins = [...]` configuration, no installation step.

Each rule subclasses `BaseASTRule` and receives the parsed Markdown document as an
**AST** (`BlockNode` tree) plus the list of **HTML nodes** extracted by the Polyglot
Extractor. This gives rules access to the full structural context of a file, not just
raw text.

---

## Quick start

This section details the specifications and guidelines for Quick start within the Zenzic ecosystem.


### 1. Create the rules directory

```bash
mkdir -p .zenzic/rules
```

### 2. Write your rule

```python title=".zenzic/rules/no_draft_heading.py"
# .zenzic/rules/no_draft_heading.py
from collections.abc import Generator
from pathlib import Path

from zenzic.core.ast import BlockNode, Heading
from zenzic.core.rules import RuleFinding
from zenzic.core.validator import HtmlNodeInfo
from zenzic.rules.base import BaseASTRule


class NoDraftHeadingRule(BaseASTRule):
    """Forbid headings that start with the word DRAFT."""

    def __init__(self) -> None:
        super().__init__(rule_id="LOCAL-001", severity="error")

    def visit_block_node(
        self,
        node: BlockNode,
        file_path: Path,
    ) -> Generator[RuleFinding, None, None]:
        if isinstance(node, Heading):
            # Serialize heading text from children
            text = "".join(
                getattr(child, "text", "") for child in node.children
            ).strip()
            if text.upper().startswith("DRAFT"):
                yield RuleFinding(
                    file_path=file_path,
                    line_no=0,   # line tracking not available at block level
                    rule_id=self.rule_id,
                    message=f"Heading '{text}' starts with DRAFT — remove before publishing.",
                    severity=self.severity,
                )

    def visit_html_node(
        self,
        node: HtmlNodeInfo,
        file_path: Path,
    ) -> Generator[RuleFinding, None, None]:
        return  # this rule does not inspect HTML nodes
        yield    # pragma: no cover — makes the function a generator
```

### 3. Run Zenzic

```bash
zenzic check all
```

Zenzic automatically loads `NoDraftHeadingRule` from `.zenzic/rules/no_draft_heading.py`
and applies it to every Markdown file. Findings appear alongside built-in Z-Codes in the
normal output.

---

## The `BaseASTRule` contract

This section details the specifications and guidelines for The BaseASTRule contract within the Zenzic ecosystem.


### Constructor

```text
BaseASTRule.__init__(
    self,
    rule_id: str,
    severity: str = "warning",   # "error" | "warning" | "note"
    max_visits: int = 10_000,    # visitation budget (see Sandbox section)
)
```

### Abstract methods

You **must** implement both abstract methods. Both are generator functions:

```python
def visit_block_node(
    self,
    node: BlockNode,
    file_path: Path,
) -> Generator[RuleFinding, None, None]:
    ...

def visit_html_node(
    self,
    node: HtmlNodeInfo,
    file_path: Path,
) -> Generator[RuleFinding, None, None]:
    ...
```

If your rule only inspects one kind of node, return immediately (or `yield` nothing) in
the other method — both must still be present.

### Available AST node types (from `zenzic.core.ast`)

| Class | Description |
|---|---|
| `Document` | Root node — wraps the whole file |
| `Heading` | `# H1` through `###### H6` — has `.level` and `.marker` |
| `Paragraph` | Block of inline content |
| `LinkNode` | `[text](url)` — has `.url` |
| `TextNode` | Plain text fragment — has `.text` |
| `CodeSpanNode` | `` `code` `` — has `.code` |
| `EmphasisNode` | `*text*` — has `.marker` |
| `StrongNode` | `**text**` — has `.marker` |

`visit_block_node` is called once for every `BlockNode` encountered during a
depth-first traversal. `Document`, `Heading`, and `Paragraph` are all `BlockNode`
subclasses.

### HTML node fields (`HtmlNodeInfo`)

`visit_html_node` is called once for every `<a>` and `<img>` tag extracted by the
Polyglot Extractor.

| Field | Type | Description |
|---|---|---|
| `.tag` | `str` | `"a"` or `"img"` |
| `.href` | `str \| None` | Value of `href` (for `<a>`) or `src` (for `<img>`). `None` if absent |
| `.line_no` | `int` | 1-based source line number |
| `.suppressed` | `bool` | `True` when `data-zenzic-ignore` is present on the tag |
| `.is_missing_href` | `bool` | `True` when `href`/`src` is absent or empty → Z121 |
| `.is_jump_link` | `bool` | `True` when `href="#"` → Z122 |
| `.unknown_attrs` | `frozenset[str]` | Attributes not in the Safe-Core list → Z120 |
| `.raw_tag` | `str` | Original tag text (for diagnostic messages) |

---

## The sandbox: deterministic visitation budget

Every call to `check()` resets an internal counter. Each time the engine visits an
AST node or an HTML node it calls `check_budget()`, which increments the counter.
If the counter exceeds `max_visits`, a `ZenzicRuleTimeout` exception is raised,
caught by the engine, and converted to a **Z902 (RULE_TIMEOUT)** finding — the rule
is skipped for that file and scanning continues.

```text
docs/guide.md:0  [Z902]  Rule 'LOCAL-001' exceeded execution limit: …
```

This design replaces thread-based or signal-based timeouts entirely, making the
sandbox **Windows-compatible** and **GIL-safe**.

!!! tip "Choosing `max_visits`"
    The default (10 000) covers any realistic documentation file. Raise it only if
    your rule legitimately needs to visit very large synthetic documents (e.g. in a
    test suite). Never disable it by passing `max_visits=0`.

Any other unhandled Python exception inside `visit_block_node` or `visit_html_node`
is caught and converted to a **Z901 (RULE_ENGINE_ERROR)** finding with the original
traceback message.

---

## Discovery and load order

At startup, `_build_rule_engine()` globs `.zenzic/rules/*.py`, sorted
alphabetically. For each file:

1. Files whose name starts with `_` are skipped (useful for shared helpers).
2. The file is imported dynamically as a fresh module.
3. Every attribute that is a **concrete subclass of `BaseASTRule`** is instantiated
   with its zero-argument constructor and added to the engine.

**Load order** (all six stages, in sequence):

1. Built-in always-active rules (Z107, Z505, Z506).
2. Z601 BRAND_OBSOLESCENCE (when `obsolete_names` is set).
3. Core rules from the `zenzic.rules` entry-point group.
4. Regex rules from `[[custom_rules]]` in `.zenzic.toml`.
5. External plugin rules from `plugins = [...]`.
6. **Custom AST Rules v2** from `.zenzic/rules/*.py`. ← API v2

Rules at stage 6 are deduplicated by `rule_id` (first registration wins).

---

## Testing your rules

Use `run_rule` or instantiate `AdaptiveRuleEngine` directly:

```python title="tests/test_local_rules.py"
from pathlib import Path
from zenzic.rules import AdaptiveRuleEngine

# Import your rule as a local module
import sys
sys.path.insert(0, ".zenzic/rules")
from no_draft_heading import NoDraftHeadingRule


def test_detects_draft_heading() -> None:
    engine = AdaptiveRuleEngine([NoDraftHeadingRule()])
    findings = engine.run(Path("guide.md"), "# DRAFT — Work in Progress\n\nSome text.\n")
    assert len(findings) == 1
    assert findings[0].rule_id == "LOCAL-001"


def test_clean_file_passes() -> None:
    engine = AdaptiveRuleEngine([NoDraftHeadingRule()])
    findings = engine.run(Path("guide.md"), "# Introduction\n\nAll good.\n")
    assert findings == []
```

!!! note "Import path"
    Because `.zenzic/rules/` is not a Python package, you must add it to `sys.path`
    manually in tests, or use `importlib.util.spec_from_file_location`. Alternatively,
    structure your tests to import the class via the auto-discovery path used by the
    engine.

---

## Rule authoring checklist

- [ ] File placed in `.zenzic/rules/` (not in `src/` or anywhere else).
- [ ] File name does **not** start with `_`.
- [ ] Class is a **concrete** subclass of `BaseASTRule` (no `@abstractmethod` left).
- [ ] Both `visit_block_node` and `visit_html_node` are implemented (even if one is empty).
- [ ] `rule_id` is unique. Use a local prefix, e.g. `"LOCAL-001"`, `"MYTEAM-001"`.
- [ ] No I/O, no network calls, no subprocess inside visitor methods.
- [ ] No mutable global state (counter class attributes, etc.).
- [ ] `max_visits` left at default unless you have a specific, documented reason.

---

## Comparison with API v1 (Plugin Rules)

| Feature | API v1 — Plugin Rules | API v2 — AST Rules |
|---|---|---|
| Distribution | Separate pip package | File in `.zenzic/rules/` |
| Registration | `plugins = [...]` in `.zenzic.toml` | Zero config — auto-discovery |
| Base class | `BaseRule` | `BaseASTRule` |
| Input | `text: str` (raw Markdown) | `BlockNode` AST + `HtmlNodeInfo` |
| Sandbox | `except Exception` → Z901 | Visitation budget → Z902 + Z901 |
| Windows safe | Yes | Yes |
| Use when | Sharing across projects | Project-local governance |

---

## See also

- [TOML Custom Rules DSL](../../how-to/add-custom-rules.md) — regex rules, no Python required
- [Writing Plugin Rules (API v1)](./write-plugin.md) — distributable entry-point plugins
- [Finding Codes — Z901 / Z902](../../reference/finding-codes.md#z901) — sandbox error codes
- [AST Foundations](../reference/ast-foundations.md) — internal AST node hierarchy
