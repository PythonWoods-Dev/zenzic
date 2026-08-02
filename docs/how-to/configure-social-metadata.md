---
sidebar_label: "Social Metadata & SEO"
description: "Configure Open Graph tags, Twitter Cards, and per-page SEO metadata in your Zensical/MkDocs project."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Configure Social Metadata & SEO

Zensical and MkDocs handle social metadata at two levels: **site-wide defaults** in `zensical.toml` (or `mkdocs.yml`), and **per-page overrides** in each Markdown file's frontmatter. This guide shows both, using Zenzic's own configuration as the reference model.

---

## Site-wide Defaults (`zensical.toml` or `mkdocs.yml`)

The global settings live in the project configuration:

```toml
# zensical.toml / mkdocs.yml
site_name = "Zenzic"
site_url = "https://zenzic.dev/"
site_description = "Documentation quality gate for Markdown projects."

# Global extra variables (like social links or default images)
[extra]
social_image = "assets/social/social-card.png"
```

!!! tip "OG image specification"
    Social card images must be **1200 × 630 px** (1.91:1 ratio). Files smaller
    than this are cropped or rejected by LinkedIn and Twitter. Use PNG for
    screenshots and SVG-exported graphics; avoid JPEG for text-heavy cards.

---

## Per-page Overrides (Frontmatter)

Any page can override the global defaults by adding fields to its frontmatter:

```markdown
---
title: "Architecture — How Zenzic Works"
description: "Deep dive into the Two-Pass Pipeline, VSM, and path traversal guard."
image: assets/social/social-card.png
keywords: [zenzic, architecture, vsm, pipeline, document integrity engine]
---
```

| Frontmatter key | Maps to | Notes |
| :--- | :--- | :--- |
| `title` | `<title>`, `og:title`, `twitter:title` | The build engine appends the site title automatically |
| `description` | `<meta name="description">`, `og:description` | Keep under 155 characters for search snippets |
| `image` | `og:image`, `twitter:image` | Absolute or root-relative; overrides site default |
| `keywords` | `<meta name="keywords">` | Comma-separated list |

---

## Storing Social Images

Place all social card assets in `docs/assets/social/` (or the folder mapped to static assets):

```text
docs/assets/social/
├── social-card.png          ← default OG image (1200 × 630, dark)
├── social-card-light.png    ← light-mode variant
├── social-card.svg          ← source SVG (do not serve directly as OG)
└── social-card-light.svg
```

!!! caution "SVG as OG image"
    Most social crawlers (LinkedIn, Slack, iMessage) do not render SVG. Always
    export a PNG from the SVG source. The SVG files are kept in `docs/assets/social/`
    as design sources only.

For page-specific cards (e.g. a blog post announcing a release), add the PNG
and reference it in the post's frontmatter:

```markdown
---
title: "Zenzic Documentation Security Platform"
image: assets/social/social-card.png
---
```

---

## Verification

After updating metadata, verify the output locally by building the documentation:

```bash
uvx uv run mkdocs build
# or
mkdocs build
```

Then inspect any page's `<head>` with browser DevTools (Elements tab, search for
`og:image`). For production verification, use the
[Twitter Card Validator](https://cards-dev.twitter.com/validator) or
[Open Graph Debugger](https://developers.facebook.com/tools/debug/) — both
accept a URL and display which tags they resolved.

---

## Zenzic & Social Assets

Zenzic does not validate external social URLs, but it **does** detect unused
static assets. If you add a custom social card PNG and never reference it in
frontmatter or configuration, Zenzic will flag it as an unused asset on the
next `zenzic check all` run.

Exclude intentional source-only files in `.zenzic.toml`:

```toml
# .zenzic.toml
excluded_assets = [
    "assets/social/*.svg",   # SVG sources — not served as OG images
]
```


## See Also

- [Why Zenzic](../explanation/why-zenzic.md)
