---

description: "Architectural rationale for using native HTML/Mermaid over static SVGs in Markdown pages."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Markdown Asset Componentization Rationale

Diagrams and structured illustrations intended for **exclusive use within Markdown pages**
must be implemented as native HTML markup or Mermaid code blocks, never as a static
text-bearing `.svg` file (Directive ZRT-DOC-010). Zenzic's documentation site is a
plain MkDocs/Material project — there is no React/JSX toolchain anywhere in this
repository, and no `mkdocs-macros-plugin` installed, so `.tsx` components and live
Jinja variable interpolation *inside a page's Markdown body* are not available
mechanisms here at all. The two real options are:

- **Native HTML**, pasted directly into the `.md` file. MkDocs passes raw HTML
  through its Markdown renderer unmodified, so inline `<svg>`/`<div>` markup
  renders exactly as written — styled with the site's real CSS custom properties
  (`--zz-*`/`--md-*`, defined in `docs/assets/css/extra.css`, keyed off
  `[data-md-color-scheme]`).
- **Mermaid code blocks** (```` ```mermaid ````, via `pymdownx.superfences`), already
  used throughout this docs site (e.g. [Sovereign Verification Model](sovereign-verification-model.md)).
  A Mermaid diagram is declarative text checked into the same file as the
  surrounding prose — diff-reviewable like any other content change, and
  re-rendered fresh by the client-side Mermaid script on every page load.

This rule exists due to several critical limitations of static `.svg` files:

- **Theme Agnosticism:** An `.svg` referenced via `<img src="...">` is opaque to
  the browser — its internal `fill`/`stroke` values are baked in at export time
  and cannot see the host page's CSS custom properties, so it needs a hand-maintained
  duplicate asset (or JS-driven swapping) to avoid looking wrong under the other
  color scheme. Inline HTML/SVG markup, by contrast, is styled by the same
  stylesheet as the rest of the page and re-colors automatically when
  `[data-md-color-scheme]` flips between `default` and `slate`.
- **i18n Barriers:** Zenzic's own i18n pipeline (`mkdocs-static-i18n`, folder or
  suffix mode) translates ordinary Markdown/HTML content — a translator edits the
  normal translated `.md`/`.<locale>.md` file, and the existing toolchain picks
  it up. Text baked into an `.svg`'s XML nodes is invisible to that pipeline
  entirely; it requires a separately hand-maintained SVG per locale, with no
  mechanism to catch the two drifting apart.
- **Data Synchronization:** A static `.svg` must be manually re-exported by hand
  whenever the diagram it depicts changes. A Mermaid block is plain text, so it
  changes in the same diff as the prose or code it documents — there is no
  separate binary artifact to remember to regenerate. (Note: this benefit comes
  from Mermaid's declarative-text nature, not from live variable interpolation —
  Markdown page content in this project is never run through Jinja2 at all;
  `{{ }}`/`{% %}` templating is only available in `overrides/*.html` theme
  templates, e.g. the homepage partials under `overrides/partials/homepage/`,
  which sit outside individual doc pages.)

---

## Permitted and Forbidden SVG Uses

| Use Case | Status | Reason |
| :--- | :---: | :--- |
| **OpenGraph Social Cards** (`docs/assets/social/`) | Permitted (✓) | Consumed directly by `<meta og:image>`, never rendered inside a page's own layout |
| **GitHub README Illustrations** | Permitted (✓) | Rendered by GitHub's Markdown processor, entirely outside the MkDocs build |
| **Pure Graphics** (logos, simple shapes) | Permitted (✓) | No text nodes or localized data requiring translation |
| **Text-Bearing Illustrations inside Markdown** | Forbidden (❌) | Must use inline HTML or a Mermaid block to support i18n and theme-reactive styling |

---

## See Also

- [Zenzic Style Guide](../reference/zenzic-style.md)
