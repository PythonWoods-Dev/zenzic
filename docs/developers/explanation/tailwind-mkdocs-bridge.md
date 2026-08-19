---
description: "How Zenzic reconciles Tailwind CSS rem scaling with MkDocs Material's font-size and syncs dark mode state."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

This section details the specifications and guidelines for the Tailwind/MkDocs bridge within the Zenzic ecosystem.

# Tailwind/MkDocs Material Bridge

This document explains the architectural pattern that allows Tailwind CSS components to coexist with MkDocs Material on the same page without layout corruption or dark-mode desynchronisation.

---

## The Problem: The 125% Font-Size Conflict

MkDocs Material applies `font-size: 125%` to the `<html>` element globally. This scales the browser's base font size from `16px` to `20px` for accessibility. Since Tailwind CSS uses `rem`-based utility classes throughout, every Tailwind value inherits this inflation:

| Tailwind class | Expected | Actual (under 125%) |
|---|---|---|
| `p-4` (`1rem`) | `16px` | `20px` |
| `text-sm` (`0.875rem`) | `14px` | `17.5px` |
| `gap-6` (`1.5rem`) | `24px` | `30px` |
| `max-w-[1400px]` | `1400px` | `1400px` ✅ (px immune) |

Fixed `px` values are immune; every `rem`-derived value is inflated by 25%. This breaks spacing rhythm, typography scale, and component proportions on all landing-page sections.

---

## The Solution: Surgical Scoped Reset

The bridge uses two cooperating components with zero server-side logic.

### 1. The CSS Targeting Rule

Added to `docs/assets/css/extra.css`:

```css
/* MkDocs Material sets html { font-size: 125% } for accessibility.
 * Reset to 100% (16px) ONLY on pages containing .zz-tailwind-root. */
html:has(.zz-tailwind-root) {
  font-size: 100% !important;
}
```

The CSS `:has()` pseudo-class fires exclusively when the DOM contains an element with the class `zz-tailwind-root`. All regular documentation pages — which do not carry this class — remain at the MkDocs Material default of 125% and are entirely unaffected.

### 2. The Semantic Anchor

The `zz-tailwind-root` class is applied to the outermost `<div>` wrapper in `overrides/home.html`:

```html
<div class="zz-tailwind-root flex flex-col min-h-screen …">
```

`zz-tailwind-root` carries no visual properties. It is a pure semantic signal whose sole function is to activate the bridge rule above.

---

## Why `:has()` and Not a Body Class?

Alternative approaches were considered and rejected:

| Approach | Rejection reason |
|---|---|
| Global `font-size: 100%` reset | Corrupts all regular doc pages (TOC, sidebar, tables, admonitions) |
| `!important` per Tailwind class | ~3,000 utility classes — unmaintainable |
| MkDocs Material `extra.body_class` | Adds per-page server configuration; couples the template to the TOML |
| CSS `@layer` scoping | Does not alter cascade specificity relative to MkDocs Material's base rule |
| Convert Tailwind to `px` everywhere | Defeats the purpose of a utility-first framework; massive maintenance surface |

The `:has()` selector is the only mechanism that is:

1. **Scoped** — fires only on the target page
2. **Pure CSS** — zero server-side state
3. **Non-invasive** — does not touch any existing style rules
4. **Browser-native** — supported in all modern evergreen browsers (Chrome 105+, Firefox 121+, Safari 15.4+)

---

## Dark Mode Sync

MkDocs Material communicates the current colour scheme via a `data-md-color-scheme` attribute on the `<body>` element:

- `data-md-color-scheme="slate"` → dark mode
- `data-md-color-scheme="default"` → light mode

Tailwind's `dark:` variant operates via the `dark` class on `<html>` by default. Since MkDocs Material owns the `<html>` element and never applies a `dark` class, the `dark:` variant is non-functional in this context.

**Resolution:** Dark-mode-aware styles for Tailwind-rendered components are written as explicit CSS rules in `extra.css` targeting `[data-md-color-scheme="slate"]`, not as `dark:` Tailwind utilities.

Example pattern:

```css
/* Correct — uses MkDocs Material's scheme attribute */
[data-md-color-scheme="slate"] .my-component {
  background-color: #0d1117;
}

/* Incorrect — Tailwind dark: never fires in this host */
/* <div class="dark:bg-[#0d1117]"> */
```

The Tailwind source files may retain `dark:` utilities for semantic clarity and future portability, but these classes have no effect at runtime. Only the `extra.css` overrides are authoritative.

---

## File Map

| File | Role |
|---|---|
| `docs/assets/css/extra.css` | Contains the `html:has(.zz-tailwind-root)` rem-reset rule |
| `overrides/home.html` | Carries the `zz-tailwind-root` semantic anchor class |
| `docs/assets/css/zenzic-tailwind.min.css` | Compiled Tailwind artifact (human-run Tailwind CLI; no Node.js in CI) |
| `overrides/partials/homepage/` | Jinja2 partials rendered inside the `zz-tailwind-root` boundary |

---

## See Also

- [Brand System Guidelines](../../how-to/use-brand-system.md)
