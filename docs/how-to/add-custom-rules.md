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

Place all `[[custom_rules]]` blocks **before** the `[build_context]` section. `[build_context]`
must be the last section in `.zenzic.toml` — TOML table headers apply to all subsequent keys, so
any top-level field written after `[build_context]` would silently become a `build_context` sub-key.

```toml
# Correct ordering
docs_dir = "docs"

[[custom_rules]]
id       = "ZZ-NODRAFT"
pattern  = "(?i)\\bDRAFT\\b"
message  = "Remove DRAFT marker before publishing."
severity = "warning"

[build_context]          # ← always last
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

All patterns are applied with Python `re.search` — a match anywhere on the line triggers the
finding. Use `^` and `$` anchors only when you need to constrain to the start or end of the line.

---

## Need structural analysis?

`[[custom_rules]]` applies a regex line-by-line. If your rule requires **AST-level access**
(e.g., inspecting heading hierarchy, counting paragraphs, or analyzing HTML tag attributes),
use the **Custom AST Rules API v2** instead:

- Drop a `.py` file in `.zenzic/rules/` — no packaging, no entry-points.
- Subclass [`BaseASTRule`](../developers/how-to/write-ast-rule.md) and implement
  `visit_block_node()` / `visit_html_node()`.

→ [Writing Custom AST Rules (API v2)](../developers/how-to/write-ast-rule.md)
