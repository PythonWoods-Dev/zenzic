---

description: "ADR 006: Fixing theme flip and Blog locale bleed in zenzic.dev — storage namespace unification and locale-sovereign navbar links."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 006: Unified Scan Scope — Storage Namespace & Blog Locale Sovereignty

> **[DEPRECATED - HISTORICAL ARCHIVE]**
> As of `v0.14.0`, the Docusaurus adapter has been permanently eradicated from the Zenzic ecosystem due to the ontological limits of static analysis on runtime-generated React ASTs. This ADR is retained strictly for historical context. See the blog post *Why We Dropped Docusaurus* for the full post-mortem.

**Status:** Deprecated (as of v0.14.0)
**Decider:** Architecture Lead
**Date:** 2026-04-27 (CEO 051, commit `3188387`)

---

## Context

This ADR is specific to the **zenzic.dev documentation site** (this repository),
not to the Zenzic CLI core. It documents two independent locale-bleed bugs that
were introduced when `future.v4: true` was activated in `docusaurus.config.ts`.

### Bug 1 — The Theme Flip

With `future.v4: true`, Docusaurus enables `siteStorageNamespacing`: it auto-generates
a per-locale localStorage key by hashing `url + baseUrl + locale`. This produced:

| Locale | localStorage key |
|--------|-----------------|
| English (`/`) | `theme-926` |
| Italian (`/it/`) | `theme-3d7` |

When a user switched from the English to the Italian documentation, their browser
loaded a **different** localStorage key. Since the Italian key had no stored
preference, Docusaurus fell back to `defaultMode: 'dark'`. If the user had
previously switched to light mode in English, the switch caused an instant
**dark mode revert** — a visible FOUC (Flash of Unstyled Content) on every
locale switch.

### Bug 2 — The Blog Locale Bleed

The Blog link in the navbar pointed to the blog using a standard Docusaurus
navbar item:

```ts
// docusaurus.config.ts — original, broken
{ to: '/blog', label: 'Journal', position: 'left' }
```

Docusaurus's static build pipeline **rewrites** both `to:` and `href:` values in
navbar items for each locale's HTML output. In the Italian static build, this
became:

```html
<!-- build/it/docs/*/index.html -->
<a href="/it/blog">Journal</a>
```

When a user navigated from Italian documentation to the Journal via that link,
they landed on `/it/blog` — which loaded the blog with the Italian locale UI:
dates rendered as `"25 aprile 2026"`, labels appeared as `"Etichette"`, the
reading time showed `"9 minuti di lettura"`. The Blog is an English-only
content space and must never be locale-translated.

Switching from `to:` to `href:` did **not** fix the issue: `href:` values in
standard navbar items are also rewritten by the Docusaurus i18n build pipeline.

---

## Decision

Two independent fixes were applied to `docusaurus.config.ts`. For step-by-step instructions on implementing these configurations, see the historical versions of the Release & Governance Protocol.

---

## Rejected Approaches

Alternative implementation designs and architectural options that were evaluated and rejected:

### `themeConfig.siteStorage.themeKey`

Proposed in the CEO directive as a way to control the storage key. This property
**does not exist** in Docusaurus 3.x. There is no `themeConfig.siteStorage`
namespace. The correct API is the top-level `storage` object.

### `respectPrefersColorScheme: true`

Also proposed in the CEO directive. This would instruct Docusaurus to follow the
OS-level color scheme preference on every page load — **overriding the user's
explicit in-app preference**. This directly reverts the CEO 149 invariant
(`respectPrefersColorScheme: false`) which was established as a permanent
protection against OS-preference-driven theme resets. It was not applied.

---

## Invariants (Non-Negotiable)

- `storage: { namespace: false }` must remain in `docusaurus.config.ts` for as

  long as `future.v4: true` is active and the Italian locale is supported.
  Removing it silently re-introduces per-locale storage key fragmentation.

- `colorMode.respectPrefersColorScheme` must remain `false`. This is an

  immutable invariant (CEO 149). Any PR that sets it to `true` is an automatic
  revert candidate.

- The Blog navbar item must remain `type: 'html'`. Converting it back to a

  standard `to:` or `href:` item will re-introduce locale bleed in the next
  build. This is not immediately visible in development mode (`npm run start`)
  because `npm run start` serves a single locale without the rewrite pipeline.
  **Bugs of this class are only visible in `just build` output.**

---

## Consequences

- Dark mode preference is now fully locale-independent. A user who sets dark mode

  in English documentation retains dark mode when switching to Italian.

- The Blog (blog) always loads at `/blog` regardless of which locale the user

  navigated from.

- The `type: 'html'` navbar item does not participate in Docusaurus's `i18n`

  translation pipeline (i.e., it does not appear in `code.json` translation keys).
  The label "Blog" is therefore hardcoded in the HTML value — this is
  intentional, as the blog is English-only and the label does not require
  translation.
