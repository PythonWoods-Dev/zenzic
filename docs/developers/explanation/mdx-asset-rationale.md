---

description: "Architectural rationale for using HTML/Jinja components instead of static SVGs in Markdown pages."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Markdown Asset Componentization Rationale

Vector assets intended for exclusive use within Markdown pages must be implemented as HTML/Jinja components (`.tsx`) rather than static `.svg` files (Directive ZRT-DOC-010).

This rule exists due to several critical limitations of static `.svg` files within a HTML/Jinja application environment:

- **Theme Agnosticism:** Static `.svg` files cannot read runtime CSS variables (like `--ifm-color-*`) or easily react to light/dark mode transitions without manual style overrides or duplicate asset files.
- **i18n Barriers:** Text inside an SVG file is baked into the XML nodes. This prevents the use of translation wrappers like `<Translate>` and requires maintaining duplicate localized files for every language.
- **Data Synchronization:** Static SVGs must be manually updated when underlying data models change, leading to technical drift and errors. HTML/Jinja components can import and dynamically render variables from a single source of truth.

## Permitted and Forbidden SVG Uses

| Use Case | Status | Reason |
| :--- | :---: | :--- |
| **OpenGraph Social Cards** (`static/assets/social/`) | Permitted (✓) | Consumed directly by `<meta og:image>`, not inside the HTML/Jinja layout |
| **GitHub README Illustrations** | Permitted (✓) | Rendered by GitHub's Markdown processor outside the build engine context |
| **Pure Graphics** (logos, simple shapes) | Permitted (✓) | No text nodes or localized data requiring translations |
| **Text-Bearing Illustrations inside Markdown** | Forbidden (❌) | Must use a `.tsx` component to support i18n and styling |


## See Also

- [Zenzic Style Guide](../reference/zenzic-style.md)
