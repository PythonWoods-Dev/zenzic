---
title: "Zenzic v0.20.0: The Extensibility Update — Custom AST Rules & Auto-Fix Expansion"
slug: zenzic-v0200-the-extensibility-update
date: 2026-07-04
authors:
  - pythonwoods
description: >
  Zenzic v0.20.0 opens the engine's AST to user-defined Python rules via the Custom Rules API v2,
  introduces a deterministic visitation sandbox, and extends the auto-fix pipeline to Z121 and Z603.
categories:
  - Releases
  - Engineering
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

!!! abstract "Architectural Update"
    *Historical Note:* This post refers to Zenzic as a "linter". As the system evolved, its capabilities expanded far beyond surface-level linting. Zenzic is now officially classified as a **Deterministic Document Integrity Engine for Markdown/MDX graphs**. Read the [latest documentation](https://zenzic.dev/) for current architectural capabilities.

Zenzic v0.20.0 is the first release to expose the engine's internal Abstract Syntax Tree to the
outside world. After v0.19.0 laid the AST foundations, The Extensibility Update answers a
long-standing question: *what if the rules I need simply don't exist yet?*

With v0.20.0, you write them yourself — in plain Python, in under a minute, with zero packaging.

<!-- more -->

## The Problem with "One Size Fits All" Governance

Every project has its own vocabulary of forbidden terms, structural patterns that signal incomplete
work, or brand conventions that no generic linter understands. Until now, Zenzic offered two
imperfect options:

- **`[[custom_rules]]` in `.zenzic.toml`:** fast and declarative, but limited to per-line regex.
  Cannot inspect headings, count nested elements, or reason about HTML tag attributes.
- **Plugin API v1 (`BaseRule`):** powerful, but requires a separate Python package, entry-point
  registration in `pyproject.toml`, and explicit activation in `.zenzic.toml`. Too much friction
  for project-local rules.

v0.20.0 introduces a third path: the **Custom Rules API v2**.

## Drop a `.py` File, Get a New Lint Rule

The design principle is radical simplicity. Create `.zenzic/rules/` in your repository, drop a
Python file inside, and Zenzic discovers it automatically at the next scan. No configuration, no
installation, no entry-points.

```python title=".zenzic/rules/no_draft_heading.py"
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
        self, node: BlockNode, file_path: Path
    ) -> Generator[RuleFinding, None, None]:
        if isinstance(node, Heading):
            text = "".join(getattr(c, "text", "") for c in node.children).strip()
            if text.upper().startswith("DRAFT"):
                yield RuleFinding(
                    file_path=file_path,
                    line_no=0,
                    rule_id=self.rule_id,
                    message=f"Heading '{text}' starts with DRAFT — remove before publishing.",
                    severity=self.severity,
                )

    def visit_html_node(
        self, node: HtmlNodeInfo, file_path: Path
    ) -> Generator[RuleFinding, None, None]:
        return
        yield  # makes the function a generator
```

Run `zenzic check all`. `NoDraftHeadingRule` is active. No other step required.

## The Sandbox: Deterministic Visitation Budget

Giving users access to the AST raises an immediate safety concern: what prevents an infinite loop
inside a custom rule from freezing the CI pipeline?

Our answer deliberately rejects the conventional approach of thread-based or signal-based timeouts.
`SIGALRM` does not work on Windows. Daemon threads, while technically functional, can degrade the
main process under the GIL when spinning on a CPU-bound loop. Both solutions introduce
non-determinism that conflicts with Zenzic's Zero Crash policy.

Instead, v0.20.0 implements a **Deterministic Visitation Budget**.

Every call to `visit_block_node` or `visit_html_node` is preceded by a call to `check_budget()`,
which increments an internal counter. If the counter exceeds `max_visits` (default: 10 000), a
`ZenzicRuleTimeout` exception is raised. The engine catches it, emits a **Z902 (RULE_TIMEOUT)**
finding, and continues to the next rule. The scan never halts.

```text
docs/reference/api.md:0  [Z902]  Rule 'LOCAL-001' exceeded execution limit (10000 visits).
```

Similarly, any unhandled Python exception inside a visitor method is caught and converted to a
**Z901 (RULE_ENGINE_ERROR)** finding with the original traceback message. One faulty rule cannot
abort the entire documentation audit.

This design is:

- **Windows-compatible** — no signals, no threads.
- **GIL-safe** — all execution is strictly single-threaded.
- **Deterministic** — the same input always produces the same budget consumption.

## Auto-Fix Expansion: Z121 and Z603

v0.20.0 also extends the `zenzic fix` pipeline with two new mutation classes.

### Z121 → Z122: MISSING_OR_EMPTY_HREF

An `<a>` tag with a missing or empty `href` is a structural error (`Z121`). In many real-world
situations — component libraries, documentation placeholders, navigation scaffolding — the author
knows the link is intentional but temporary.

`zenzic fix` now rewrites:

```html
<a>View details</a>
<!-- becomes -->
<a href="#">View details</a>
```

This converts the hard error (`Z121`) to a warning (`Z122 JUMP_LINK`), keeping the markup valid
and CI green while the final destination is determined. The `Z122` finding remains visible in the
report, so the debt is never silently buried.

### Z603: Dead Suppression Auto-Removal

A `<!-- zenzic:ignore: Zxxx -->` comment becomes "dead" when the finding it was suppressing no
longer exists. Dead suppressions are governance debt: they signal that the documentation was
previously broken at that location, but no one cleaned up the annotation.

`zenzic fix` now surgically removes dead suppression comments and `data-zenzic-ignore` HTML
attributes. The removal is byte-precise — no surrounding whitespace or newlines are disturbed.

## The `fixable` Metadata Field

To make the auto-fix surface discoverable, v0.20.0 adds a `fixable: bool` field to every
`CodeDefinition` in the registry. Run `zenzic explain Z121` to see it:

```text
┌──────────────────┬────────────────────────────────────────────────────────────┐
│ Code             │ Z121                                                       │
│ Name             │ MISSING_OR_EMPTY_HREF                                      │
│ Severity         │ Error                                                      │
│ Tier             │ Core                                                       │
│ Fixable          │ Yes                                                        │
│ Description      │ <a> tag has a missing or empty href attribute.             │
└──────────────────┴────────────────────────────────────────────────────────────┘
```

The `finding-codes.md` reference page now carries **Fixable: Yes** badges for Z108, Z121, and Z603.

## The "Dogfooding Paradox" & HTML Suppression

During the validation of Zenzic's own documentation, we encountered a unique engineering puzzle: testing links to feed files (like RSS or Atom) that are dynamically generated at build time. Since these files do not exist during the linting stage, they trigger a `Z104 (FILE_NOT_FOUND)` error.

Applying `data-zenzic-ignore` to raw HTML `<a>` tags correctly suppresses HTML hygiene findings (`Z12x`), but the link resolver pipeline (URP) still attempted to resolve the link, triggering a persistent `Z104` leak.

In v0.20.0, we resolved this by short-circuiting the resolver pipeline for suppressed HTML nodes. If `node.suppressed` is true, Zenzic bypasses URP resolution entirely for that element, and updates the `SuppressionTracker` to mark the `DATA-ZENZIC-IGNORE` directive as consumed, preventing `Z603 (DEAD_SUPPRESSION)` warnings from firing.

## Strict Architectural Invariants Preserved

v0.20.0 did not bend any of the engine's core constraints:

| Invariant | Status |
|---|---|
| Zero Subprocess | ✅ Maintained — no `subprocess.Popen` or `os.system` |
| $O(N)$ DFA guarantee | ✅ Maintained — custom rules operate on already-parsed AST |
| No Inference runtime | ✅ Maintained — no new ML dependencies |
| Zero Crash policy | ✅ Maintained — Z901/Z902 absorb all custom rule failures |
| Single-threaded sandbox | ✅ Maintained — no `ThreadPoolExecutor`, no `SIGALRM` |

## What's Next

To start writing your own custom rules, consult the [Custom Rules API v2 Guide](../../developers/how-to/write-ast-rule.md). For a complete list of changes, see the [v0.20.0 Release Notes](https://github.com/PythonWoods/zenzic/releases/tag/v0.20.0).

---

Full release notes: [CHANGELOG.md — v0.20.0](https://github.com/PythonWoods/zenzic/blob/main/CHANGELOG.md)
Custom AST Rules guide: [Writing Custom AST Rules (API v2)](../../developers/how-to/write-ast-rule.md)
Finding codes reference: [Z901 / Z902](../../reference/finding-codes.md)
