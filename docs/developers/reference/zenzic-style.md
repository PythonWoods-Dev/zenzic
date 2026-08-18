---
description: "Documentation writing standards and formatting rules for Zenzic contributors."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Zenzic Style Guide

> *"The rigour applied to code must extend to every pixel the user sees."*

This document codifies the **Zenzic Visual Language** — the binding rules
for all Zenzic documentation pages. Every contributor must follow these
rules. Reviewers must reject PRs that violate them.

**Directive:** ZRT-DOC-002

---

## 1. Card Rule (High-Density UX) {#card-rule}

Navigation cards orient. They do **not** replace the sidebar.

### Structure

Every card in a `<div class="grid cards" markdown>` block must have exactly:

1. An **icon** (`:material-*: / :octicons-*:` — see §3).
2. A **bold title**.
3. A **description** of at most two lines.
4. A **single action link** using the arrow prefix.

### Canonical example

```markdown
- :material-play: &nbsp; **User Guide**

    Everything you need to install, configure, and integrate Zenzic into
    your CI/CD workflow.

    [:material-arrow-right: Explore the Guide](../../../how-to/install.md)
```

### Forbidden patterns

| Pattern | Why |
| :--- | :--- |
| React JSX `<Icon name="..." />` | **Strictly Forbidden.** Unrendered HTML tag in Material for MkDocs. |
| Horizontal link chains (`·`-separated) | Creates a wall of text; impossible to scan |
| Nested `<li>` lists inside a card | Breaks card height uniformity |
| `---` separators inside a card | Adds visual noise without information gain |
| Cards with zero action links | Dead-end; the user has nowhere to go |

---

## 3. Iconography Law (Material for MkDocs) {#iconography}

This section details the specifications and guidelines for 3. Iconography Law (Material for MkDocs) within the Zenzic ecosystem.

### Native Emoji & Icon Shortcodes

Every icon in the documentation MUST be rendered using native Material for MkDocs shortcodes:

```markdown
:material-icon-name:
:octicons-icon-name-16:
```

Examples:

- `:material-bug-outline:`
- `:material-file-document-edit-outline:`
- `:material-sparkles:`
- `:octicons-git-pull-request-16:`
- `:material-arrow-right:`

### Rules

- **Strict No-JSX Rule**: React JSX `<Icon name="..." />` tags are strictly forbidden and will be flagged by linting.
- **Semantic consistency**: If an icon represents "Contribute" on one page, it must be the same icon on every page.
- **Uniform syntax**: Every icon in a card grid uses native `:material-*: / :octicons-*:` shortcodes.
- **No emoji in headings**: Emoji characters (`⚡`, `🛡️`, `🚀`, etc.) are permitted in running prose only. They must not be used as heading prefix decorators. Heading hierarchy communicates document structure; emoji communicates marketing enthusiasm. These are incompatible roles. Headings containing emoji will be rejected in PR review.

---

## 4. Anchor ID Protocol (ZRT-DOC-004) {#anchor-ids}

This section details the specifications and guidelines for 4. Anchor ID Protocol (ZRT-DOC-004) within the Zenzic ecosystem.

### When to add explicit IDs

Add `{#id}` to a heading when it satisfies **both** of:

1. It is an **H2 or H3** heading (never H1 — some engines auto-generate H1 IDs from sidebar labels).
2. It is referenced by a cross-page link (`[text](page.md#anchor)`).

### i18n Invariant

The canonical ID is always the **English slug**. Italian (and any future
language) pages must use the same `{#id}` value:

```markdown
<!-- * EN * -->
## Getting Started {#getting-started}

<!-- * IT * -->
## Inizia Ora {#getting-started}
```

This ensures the VSM resolver and cross-language links never break due to
translation-dependent slug generation.

### Heading format

```markdown
## Section Title {#section-title}
```

Do not add IDs to headings that are never linked to externally. Every
explicit ID is a maintenance contract.

---

## 5. Code Block Rule {#code-blocks}

Every opening fence **must** carry a language tag:

| Fence | Verdict |
| :--- | :---: |
| ` ```python ` | ✓ |
| ` ```bash ` | ✓ |
| ` ```toml ` | ✓ |
| ` ```text ` | ✓ (plain output) |
| ` ``` ` | ✗ **FORBIDDEN** |

Use `text` for output that has no syntax highlighting. Naked fences hurt
accessibility tools and syntax highlighters.

**Gutter specificity:** for CLI output shown inside `:::info` blocks,
always use the `text` tag to prevent the syntax highlighter from generating
random colours on log strings or file paths.

---

## 6. SPDX Header {#spdx-header}

Every source documentation file (`.md`, `.md`, and equivalent content files)
must carry SPDX metadata.

Minimum header pattern:

```html
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
```

Files with YAML frontmatter place the SPDX block immediately after the
closing `---`.

### Significant Contribution Rule (MUST)

For significant changes (new logic, major content blocks, structural rewrites),
contributors **must** add their own `SPDX-FileCopyrightText` line below the
project line.

```html
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-FileCopyrightText: 2026 Contributor Name <contributor@example.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
```

Trivial edits (typos, punctuation, formatting-only changes) do not require an
additional contributor line.

### Legal Governance Model

Zenzic does **not** require a CLA transfer model. Governance is based on:

- **DCO** (Developer Certificate of Origin) for authorship attestation.
- **REUSE/SPDX** for per-file copyright and license traceability.

Contributors retain copyright on significant changes and declare authorship via
SPDX headers.

---

## 7. Visual Consistency Checklist {#checklist}

Before submitting a PR, verify:

- [ ] Every card grid follows §1 (single action link).
- [ ] Every admonition matches its §2 role.
- [ ] All icons use native `:material-*: / :octicons-*:` shortcodes — no React JSX `<Icon />` tags remain.

- [ ] Any new icon name is registered in `src/components/Icon.tsx` (§3).
- [ ] Cross-referenced H2/H3 headings have explicit `{#id}` (§4). No anchors on H1.
- [ ] No naked code fences exist (§5).
- [ ] SPDX header is present (§6).
- [ ] No hex literal (`#rrggbb`) in `src/` outside `ZenzicPalette._*` (§9).
- [ ] All colour references use `ZenzicPalette.*` — no removed flat constants (§9).
- [ ] No new `.svg` file added to `docs/assets/terminal/` (§10).
- [ ] Any text-bearing SVG inside an Markdown page is implemented as `.tsx` (§10).

---

## 8. ZenzicUI Gateway {#zenzicui-gateway}

All branded terminal output in Zenzic flows through a single object: `ZenzicUI` in
`src/zenzic/ui.py`. Command modules must **never** instantiate `Console` or `ZenzicUI`
directly — they must call `get_ui()` and `get_console()` from `zenzic.cli._shared`.

### Core methods

| Method | When to use |
| :--- | :--- |
| `print_header(version)` | The top-of-output Zenzic Frame banner — once per command invocation |
| `make_panel(content, *, title, border_style)` | Styled Rich `Panel` — for structured output blocks |
| `print_exception_alert(message, *, context, title, border_style)` | Error panels for `ZenzicError` and `PluginContractError` |

### Usage pattern

```python
# In any _check.py / _clean.py / _standalone.py command
from . import _shared

# Print the Zenzic banner header
_shared.get_ui().print_header(__version__)

# Print a styled panel
panel = _shared.get_ui().make_panel(
    "Content here",
    title="Panel Title",
    border_style="bold cyan",
)
_shared.get_console().print(panel)
```

### Why the gateway matters

The `--no-color` and `--force-color` CLI flags call `configure_console()`, which atomically
replaces the module-level `console` and `_ui` singletons. Any locally-created `Console` or
`ZenzicUI` instance will be frozen before the flag takes effect, silently ignoring the
user's color preference.

The `force_terminal` parameter must **always** be `None` (auto-detect) in the module-level
`Console`, never `False`. Explicit `False` disables color system detection entirely —
resulting in no ANSI styling even in truecolor terminals. This is the most common source of
visual regressions in the Zenzic CLI layer.

### Checklist addition

Add to your PR checklist:

- [ ] No `Console(...)` or `ZenzicUI(...)` instantiation in command modules.
- [ ] All banner output uses `get_ui().print_header()`, not a locally-created UI instance.
- [ ] `force_terminal` on any new `Console` call is `None` or conditional (`True if ... else None`), never `False`.

---

## 9. ZenzicPalette — Zero Hex Law {#zenzic-palette}

`ZenzicPalette` in `src/zenzic/ui.py` is the **sole authorised source of colour values**
in the entire Zenzic codebase. This is the Zero Hex Law.

### The Law

!!! warning "Design Constraint"

    No hex colour string (e.g. `#4f46e5`) and no raw Rich colour name (e.g. `"red"`, `"cyan"`)
    may appear anywhere in `src/` **except** inside `ZenzicPalette._*` private class attributes.
    Every other file must address only the semantic public attributes shown below.

### Semantic palette

| Attribute | Hex | Meaning |
| :--- | :---: | :--- |
| `ZenzicPalette.BRAND` | `#4f46e5` | Zenzic primary / brand accent (Indigo) |
| `ZenzicPalette.SUCCESS` | `#10b981` | OK · clean · pass (Emerald) |
| `ZenzicPalette.WARNING` | `#f59e0b` | Caution · advisory (Amber) |
| `ZenzicPalette.ERROR` | `#f43f5e` | Failure · broken links (Rose) |
| `ZenzicPalette.DIM` | `#64748b` | Muted · secondary text (Slate) |
| `ZenzicPalette.FATAL` | `#8b0000` | Security breach · path traversal (Critical Red) |

### Pre-composed style strings

For the most common combinations, use a `STYLE_*` constant instead of constructing
`f"bold {X}"` inline:

| Constant | Expands to |
| :--- | :--- |
| `ZenzicPalette.STYLE_BRAND` | `"bold #4f46e5"` |
| `ZenzicPalette.STYLE_OK` | `"bold #10b981"` |
| `ZenzicPalette.STYLE_WARN` | `"bold #f59e0b"` |
| `ZenzicPalette.STYLE_ERR` | `"bold #f43f5e"` |
| `ZenzicPalette.STYLE_DIM` | `"#64748b"` |

### Usage pattern

```python
# CORRECT — semantic alias via ZenzicPalette
from zenzic.ui import ZenzicPalette

table = Table(border_style=ZenzicPalette.DIM, header_style=ZenzicPalette.STYLE_BRAND)
text = Text.from_markup(f"[{ZenzicPalette.BRAND}]Zenzic[/]")
panel = Panel("...", border_style=ZenzicPalette.STYLE_ERR)
```

```python
# FORBIDDEN — hex literal outside ZenzicPalette
text = Text.from_markup("[#4f46e5]Zenzic[/]")   # ✗

# FORBIDDEN — flat constant import (removed in)
from zenzic.ui import INDIGO, EMERALD            # ✗

# FORBIDDEN — inline alias
P = ZenzicPalette                              # ✗  use full qualification
```

### Updating the palette

To change a colour, edit **only** the corresponding `_PRIVATE` hex attribute inside
`ZenzicPalette` in `src/zenzic/ui.py`. All semantic aliases and pre-composed style
strings derive from those private attributes — the entire codebase updates automatically.

### Checklist addition

Add to your PR checklist:

- [ ] No hex literal (`#rrggbb`) anywhere in `src/` outside `ZenzicPalette._*`.
- [ ] No raw Rich colour names (`"red"`, `"cyan"`) for brand-palette usage — use `ZenzicPalette.*`.
- [ ] No local alias `P = ZenzicPalette` — always use the full class name.
- [ ] No `from zenzic.ui import INDIGO` (or any removed flat constant).

---

## 10. Markdown Asset Componentization Law {#mdx-asset-componentization}

**Directive:** ZRT-DOC-010

!!! warning "Design Constraint"

    Any vector asset intended for **exclusive use within Markdown pages** must be implemented
    as a HTML/Jinja component (`.tsx`), never as a static `.svg` file.

For the detailed architectural rationale behind this directive, see [Markdown Asset Componentization Rationale](../explanation/mdx-asset-rationale.md).

### Checklist addition

Add to your PR checklist:

- [ ] No new `.svg` file added to `docs/assets/terminal/` (use a `.tsx` component).
- [ ] Any text-bearing SVG introduced inside an Markdown page is implemented as `.tsx`.
