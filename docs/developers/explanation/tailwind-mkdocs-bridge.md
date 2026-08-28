---
description: "How Zenzic reconciles Tailwind CSS rem scaling with MkDocs Material's font-size and syncs dark mode state."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

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

## The Solution: A Reset Scoped to the Wrapper, Not `<html>`

The bridge uses two cooperating components with zero server-side logic.

### 1. The CSS Reset Rule

Added to `docs/assets/css/extra.css`:

```css
/* MkDocs Material sets html { font-size: 125% } for accessibility.
 * This blows up Tailwind's rem values by 25%.
 * Reset applied directly to the landing page wrapper (not html) to avoid
 * corrupting MkDocs Material's global header proportions. */
.zz-tailwind-root {
  font-size: 16px !important;
}
```

The reset targets `.zz-tailwind-root` **directly**, not `html:has(.zz-tailwind-root)`. Only elements *inside* the wrapper inherit the `16px` base — the MkDocs Material header, sidebar, and TOC, which live outside the wrapper in the DOM, are untouched and keep the site's normal `125%` accessibility scaling. A `:has()`-based reset on `<html>` would flip the base font-size for the *entire page* whenever the wrapper is present anywhere in it, corrupting exactly the header proportions this rule is designed to leave alone.

### 2. The Semantic Anchor

The `zz-tailwind-root` class is applied to the outermost `<div>` wrapper in `overrides/home.html`:

```html
<div class="zz-tailwind-root flex flex-col min-h-screen …">
```

`zz-tailwind-root` is the reset's own target *and* a semantic anchor other rules key off of — including one genuine, narrower use of `:has()` on this page: hiding the header's GitHub stats widget only when the wrapper is present, without touching the widget on any other page:

```css
/* Hide GitHub stats widget on the Landing Page to reduce visual noise */
html:has(.zz-tailwind-root) .md-header__source {
  display: none !important;
}
```

This is a display toggle, not a font-size reset — `:has()` is the right tool here precisely because the effect (hide one header element) is meant to apply page-wide once the wrapper is present, the opposite of the scoping goal the rem fix needed.

---

## Why a Direct Reset and Not `html:has()`?

Alternative approaches were considered and rejected:

| Approach | Rejection reason |
|---|---|
| `html:has(.zz-tailwind-root) { font-size: 100% }` | Resets the *entire* page's base font-size, including the MkDocs Material header/sidebar/TOC outside the wrapper — the exact corruption this fix exists to avoid |
| Global `font-size: 100%` reset (no scoping at all) | Corrupts all regular doc pages (TOC, sidebar, tables, admonitions) |
| `!important` per Tailwind class | ~3,000 utility classes — unmaintainable |
| MkDocs Material `extra.body_class` | Adds per-page server configuration; couples the template to the TOML |
| Convert Tailwind to `px` everywhere | Defeats the purpose of a utility-first framework; massive maintenance surface |

A reset scoped directly to `.zz-tailwind-root` is the only approach that is:

1. **Scoped to the wrapper's own subtree** — not the whole page
2. **Pure CSS** — zero server-side state
3. **Non-invasive** — does not touch any existing style rules outside the wrapper
4. **Simple** — a single class selector, no `:has()` needed for this particular rule

`:has()` remains genuinely useful elsewhere on this page (the GitHub-widget toggle above, and unrelated `.zz-hero` layout rules in the same stylesheet) — it is supported in all modern evergreen browsers (Chrome 105+, Firefox 121+, Safari 15.4+, verified against [caniuse.com](https://caniuse.com/css-has)). It was deliberately *not* used for the rem-scaling fix itself, where a plain class selector already does the job with a tighter, more predictable scope.

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
| `docs/assets/css/extra.css` | Contains the `.zz-tailwind-root` rem-reset rule and the `html:has(.zz-tailwind-root)` header-widget-hide rule |
| `overrides/home.html` | Carries the `zz-tailwind-root` semantic anchor class |
| `docs/assets/css/zenzic-tailwind.min.css` | Compiled Tailwind artifact (human-run Tailwind CLI; no Node.js in CI) |
| `overrides/partials/homepage/` | Jinja2 partials rendered inside the `zz-tailwind-root` boundary |

---

## See Also

- [Brand System Guidelines](../../how-to/use-brand-system.md)
