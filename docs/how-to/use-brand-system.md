---
description: "How to use Zenzic's semantic tokens in HTML/Jinja components and Markdown."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Use the Brand System

The Zenzic visual language is token-first. All UI colors must be consumed through semantic CSS variables defined in `src/css/custom.css`.

## HTML/Jinja components Contract

Every HTML/Jinja component must use `var(--zenzic-*)` tokens for:

1. Surface/background
2. Text hierarchy
3. Borders and outlines
4. Semantic states (`success`, `warning`, `error`, `fatal`)

### Approved token families

- `--zenzic-brand-*` for action identity and active emphasis
- `--zenzic-ink-*` for text contrast hierarchy
- `--zenzic-bg-*` for translucent layered surfaces
- `--zenzic-border-*` for separators and component framing
- `--zenzic-success|warning|error|fatal` for severity semantics

### HTML/Jinja usage example

```html
<span style="background-color: var(--zenzic-brand); color: var(--zenzic-ink-100); border: 1px solid var(--zenzic-border-brand-35); border-radius: 6px; padding: 0.2rem 0.5rem; font-weight: 600;">
  audit: passed
</span>
```

!!! danger "Policy Gate"
    UI pull requests are rejected if HTML/Jinja or local CSS introduces hardcoded color literals. Use semantic tokens only.

## Markdown Integration Pattern

Use Markdown documentation as the normative source of truth for brand token mapping.

Recommended pattern:

1. Explain policy and token mapping in Markdown.
2. Maintain CSS custom properties in `docs/assets/css/extra.css`.
3. Keep tokens and documentation aligned when making design system decisions.

## Accessibility Baseline

The palette is tuned for documentation readability first.

1. Body text must stay in Zinc tiers (`--zenzic-ink-*`) to preserve long-read comfort.
2. Brand Indigo is for interaction and active state cues, not full-paragraph prose.
3. Severity colors must remain semantic and not be reused as decorative accents.

## A/B Palette Profiles

Two optional profiles are available in `src/css/custom.css` for visual validation without component refactors.

### Activation

Set one of these attributes on `<html>`:

```html
<html data-zenzic-palette="corporate-calm">
<html data-zenzic-palette="technical-neon">
```

### Advantages and disadvantages

1. Corporate Calm
Pros: stronger enterprise tone, lower visual fatigue in long reading sessions, safer default for mixed audiences.
Cons: lower perceived energy on marketing-like surfaces, less aggressive CTA pop.

2. Technical Neon
Pros: higher perceived modernity, stronger active/hover cues, more memorable interaction identity.
Cons: can feel more intense on dense pages, requires stricter accessibility QA on edge states.

## Brand Asset Reference

The following assets are tracked by Zenzic to ensure they remain in the Virtual Site Map without suppression (resolving Z405):

- [Favicon](../favicon.ico)
- [Icon (SVG)](../assets/brand/svg/zenzic-icon.svg)
- [Logo (SVG)](../assets/brand/svg/zenzic-logo.svg)
- [Logo Dark (SVG)](../assets/brand/svg/zenzic-logo-dark.svg)
- [Logo (PNG)](../assets/brand/png/zenzic-logo.png)
- [Logo Dark (PNG)](../assets/brand/png/zenzic-logo-dark.png)

### Barlow Fonts

- [Barlow 300 Italic](../assets/fonts/barlow-condensed-300-italic.woff2)
- [Barlow 300 Normal](../assets/fonts/barlow-condensed-300-normal.woff2)
- [Barlow 600 Normal](../assets/fonts/barlow-condensed-600-normal.woff2)
- [Barlow 700 Normal](../assets/fonts/barlow-condensed-700-normal.woff2)

### IBM Plex Mono Fonts

- [IBM Plex Mono 400 Italic](../assets/fonts/ibm-plex-mono-400-italic.woff2)
- [IBM Plex Mono 400 Normal](../assets/fonts/ibm-plex-mono-400-normal.woff2)
- [IBM Plex Mono 500 Normal](../assets/fonts/ibm-plex-mono-500-normal.woff2)

### Inter Fonts

- [Inter 400 Normal](../assets/fonts/inter-400-normal.woff2)
- [Inter 500 Normal](../assets/fonts/inter-500-normal.woff2)
- [Inter 600 Normal](../assets/fonts/inter-600-normal.woff2)
- [Inter 700 Normal](../assets/fonts/inter-700-normal.woff2)

### JetBrains Mono Fonts

- [JetBrains Mono 400 Italic](../assets/fonts/jetbrains-mono-400-italic.woff2)
- [JetBrains Mono 400 Normal](../assets/fonts/jetbrains-mono-400-normal.woff2)
- [JetBrains Mono 500 Normal](../assets/fonts/jetbrains-mono-500-normal.woff2)

### Roboto Fonts

- [Roboto 300 Italic](../assets/fonts/roboto-300-italic.woff2)
- [Roboto 300 Normal](../assets/fonts/roboto-300-normal.woff2)
- [Roboto 400 Italic](../assets/fonts/roboto-400-italic.woff2)
- [Roboto 400 Normal](../assets/fonts/roboto-400-normal.woff2)
- [Roboto 700 Italic](../assets/fonts/roboto-700-italic.woff2)
- [Roboto 700 Normal](../assets/fonts/roboto-700-normal.woff2)

### Roboto Mono Fonts

- [Roboto Mono 400 Italic](../assets/fonts/roboto-mono-400-italic.woff2)
- [Roboto Mono 400 Normal](../assets/fonts/roboto-mono-400-normal.woff2)
- [Roboto Mono 700 Italic](../assets/fonts/roboto-mono-700-italic.woff2)
- [Roboto Mono 700 Normal](../assets/fonts/roboto-mono-700-normal.woff2)
