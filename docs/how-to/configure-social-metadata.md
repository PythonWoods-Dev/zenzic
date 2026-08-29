---
description: "Configure Open Graph tags, Twitter Cards, and per-page SEO metadata in your Zensical/MkDocs project."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Configure Social Metadata & SEO

Material for MkDocs has no built-in mechanism that automatically turns frontmatter into
`<meta property="og:*">` tags — this is a common misconception. There are two genuinely
separate, real mechanisms, and both need to be set up explicitly:

1. The **`social` plugin** generates card **images** (the preview picture), configured
   through `mkdocs.yml` and per-page frontmatter.
2. A **template override** is required to actually emit the `<meta>` tags a page's
   `<head>` needs for those images (and the page's title/description) to show up when a
   link is shared — the `social` plugin does not do this on its own.

Skipping step 2 is the most common mistake: card images get generated, but no meta tags
point to them, so shared links still render as plain text on social platforms.

---

## Step 1 — Generate card images with the `social` plugin

Enable it in `mkdocs.yml`:

```yaml title="mkdocs.yml"
plugins:
  - social:
      cards_layout_options:
        background_color: "#4f46e5"
```

The plugin auto-generates a `1200×630` card image per page. `cards_layout_options.title`
and `.description` default to the page's `title`/frontmatter `description` — set them
per-page if you want a different layout for a specific page:

```markdown title="docs/example.md"
---
description: "Deep dive into the Two-Pass Pipeline, VSM, and path traversal guard."
---
```

!!! tip "OG image specification"
    Generated cards are `1200 × 630 px` (1.91:1 ratio), matching what LinkedIn and
    Twitter expect — no manual sizing needed when using the plugin.

---

## Step 2 — Emit the actual meta tags

The plugin's generated images live under `assets/images/social/<page-path>.png`, but
nothing points to them until you add an `extrahead` block to a custom theme template:

```html title="overrides/main.html"
{% extends "base.html" %}

{% block extrahead %}
  {{ super() }}
  {% set title = page.meta.title if page and page.meta and page.meta.title else (page.title if page else config.site_name) %}
  {% set description = page.meta.description if page and page.meta and page.meta.description else config.site_description %}
  {% if page and page.meta and page.meta.image %}
    {% set og_image = config.site_url ~ page.meta.image %}
  {% else %}
    {% set og_image = config.site_url ~ "assets/images/social/" ~ page.url ~ ".png" %}
  {% endif %}
  <meta property="og:type" content="website" />
  <meta property="og:title" content="{{ title }}" />
  <meta property="og:description" content="{{ description }}" />
  <meta property="og:url" content="{{ page.canonical_url }}" />
  <meta property="og:image" content="{{ og_image }}" />
  <meta name="twitter:card" content="summary_large_image" />
{% endblock %}
```

A page's own `image:` frontmatter key, when set, overrides the plugin's auto-generated
card for that one page — otherwise the auto-generated path is used.

Set `custom_dir: overrides` under `theme:` in `mkdocs.yml` if you haven't already, so
MkDocs picks up this template.

---

## Per-page Overrides (Frontmatter)

The template above reads two frontmatter keys per page:

| Frontmatter key | Read by | Notes |
| :--- | :--- | :--- |
| `title` | `extrahead` override (`og:title`), `social` plugin's card layout | Falls back to the page's rendered title, then `site_name` |
| `description` | `extrahead` override (`og:description`), `social` plugin's card layout | Keep under 155 characters for search snippets |
| `image` | `extrahead` override (`og:image`) | Optional — overrides the `social` plugin's auto-generated card for this page only |

There is no built-in `<meta name="keywords">` emission in Material for MkDocs — a
`keywords` frontmatter key, if you set one, has no effect unless your own `extrahead`
override reads it explicitly.

---

## Storing a Custom Social Image

Most pages don't need this — the `social` plugin's auto-generated card is enough. For a
page that deserves its own custom image (e.g. a blog post announcing a release), place a
PNG under `docs/assets/social/` and reference it via the page's `image:` frontmatter key,
which the `extrahead` override above already checks for:

```text
docs/assets/social/
└── release-announcement.png   ← custom OG image (1200 × 630)
```

```markdown title="docs/blog/posts/release-announcement.md"
---
title: "Zenzic Documentation Security Platform"
image: assets/social/release-announcement.png
---
```

!!! caution "SVG as OG image"
    Most social crawlers (LinkedIn, Slack, iMessage) do not render SVG. If you design the
    image as an SVG source, export it to PNG before referencing it in frontmatter — never
    point `image:` at the `.svg` file directly.

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
static assets (`Z405`). Its asset-reference scanner recognizes real
Markdown/HTML links (`[text](path)`, `<img src="...">`, `<a href="...">`) and
the frontmatter `image:` key shown above — a custom social image referenced
only that way is correctly counted as used and will not be flagged.

The `social` plugin's auto-generated card images never trigger `Z405` at all —
they're written to the *built* site output during `mkdocs build`, not stored
as source files under `docs/`, so Zenzic's scan of your source tree never
sees them. SVG source files kept only as design originals for a custom image
(never directly referenced by any page, since `image:` should point at the
exported PNG) still need explicit exclusion:

```toml
# .zenzic.toml
excluded_assets = [
    "assets/social/*.svg",   # SVG sources — not served as OG images, never referenced
]
```

The same key is available under `[tool.zenzic]` in `pyproject.toml`:

```toml title="pyproject.toml"
[tool.zenzic]
excluded_assets = ["assets/social/*.svg"]
```

---

## See Also

- [Why Zenzic](../explanation/why-zenzic.md)
