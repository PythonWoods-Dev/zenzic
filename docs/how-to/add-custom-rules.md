---
description: "Define project-specific lint rules in .zenzic.toml using the Custom Rules DSL."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Add Custom Lint Rules

`[[custom_rules]]` lets you declare project-specific lint rules directly in `.zenzic.toml`. Each
rule applies a regular expression line-by-line to every `.md` file and produces a finding when
the pattern matches. No Python is required — the DSL is pure TOML.

> For the full field reference, severity matrix, and output format, see [Configuration Reference — `[[custom_rules]]`](../reference/configuration-reference.md#custom-rules).

---

## Syntax

```toml
[[custom_rules]]
id       = "ZZ-NOINTERNAL"
pattern  = "internal\\.corp\\.example\\.com"
message  = "Internal hostname must not appear in public documentation."
severity = "error"

[[custom_rules]]
id       = "ZZ-NODRAFT"
pattern  = "(?i)\\bDRAFT\\b"
message  = "Remove DRAFT marker before publishing."
severity = "warning"
```

Each `[[custom_rules]]` header appends one rule to the list. Use double brackets — that is the
TOML array-of-tables syntax.

---

## TOML placement

Root-level keys (like `docs_dir`) must precede any table header — TOML applies a table header to
all subsequent keys, so a top-level field written after any `[section]` would silently become
that section's sub-key. `[[custom_rules]]` blocks can go anywhere after the root-level keys;
there is no required ordering relative to `[build_context]` specifically.

```toml
# Correct ordering — root keys first, tables in any order after that
docs_dir = "docs"

[[custom_rules]]
id       = "ZZ-NODRAFT"
pattern  = "(?i)\\bDRAFT\\b"
message  = "Remove DRAFT marker before publishing."
severity = "warning"

[build_context]
engine = "mkdocs"
```

---

## Pattern tips

| Goal | Pattern |
| :--- | :--- |
| Case-insensitive word boundary | `(?i)\bTEST\b` |
| Literal dot (hostname) | `internal\.corp\.example\.com` |
| Match anywhere on line | `EXAMPLE` (no anchors needed — matching is per-line) |
| Exclude false positives | Use word boundaries `\b` to avoid matching `EXAMPLES` when looking for `EXAMPLE` |

Patterns are compiled with **RE2** (`zenzic.core.regex`, ADR-013), not Python's `re` module — a
match anywhere on the line triggers the finding. Use `^` and `$` anchors only when you need to
constrain to the start or end of the line. RE2 does not support lookaheads, lookbehinds, or
backreferences; a pattern using them fails at config-load time rather than matching unexpectedly.

---

## Need structural analysis?

`[[custom_rules]]` applies a regex line-by-line. If your rule requires **AST-level access**
(e.g., inspecting heading hierarchy, counting paragraphs, or analyzing HTML tag attributes),
use the **Custom Rule SDK v3** instead:

- Drop a `.py` file in `.zenzic/rules/` for auto-discovery, or register it explicitly via
  `[[custom_rules]] class_name = "my_module.my_rules.MyRule"` in `.zenzic.toml`.
- Subclass `ZenzicRuleV3` and declare a typed `RuleMetadata`.

The legacy v2 API (`BaseASTRule`) was hard-deprecated and removed in v0.28.0 — instantiating a v2
rule now raises `PluginContractError` at load time.

→ [Writing Custom Rules (Custom Rule SDK v3)](../developers/how-to/write-ast-rule.md)
