---
description: "How Zenzic's asset-reference checker interacts with social card images — setup itself is Material for MkDocs' job."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Configure Social Metadata & SEO

Zenzic does not configure or validate Open Graph tags, Twitter Cards, or social card
images — that's your build engine's job. For Material for MkDocs, see the official
[Setting up social cards](https://squidfunk.github.io/mkdocs-material/setup/setting-up-social-cards/)
documentation for the real setup mechanics (the `social` plugin, and the template
override needed to emit the actual `<meta property="og:*">` tags).

What Zenzic *does* touch is asset usage: if you reference a custom social card image
through a page's `image:` frontmatter key, `Z405` (`UNUSED_ASSET`) correctly recognizes
that reference and won't flag the file — no extra configuration needed for that case.

---

## Excluding design-source files

Auto-generated card images (from the `social` plugin) are written to the *built* site
output, not stored as source files under `docs/`, so they never reach Zenzic's scan at
all. If you keep an SVG design source for a custom card image but only ever reference the
exported PNG in frontmatter, the SVG itself is never referenced by any page and needs
explicit exclusion:

```toml title=".zenzic.toml"
excluded_assets = [
    "assets/social/*.svg",   # SVG design sources — never directly referenced
]
```

The same key is available under `[tool.zenzic]` in `pyproject.toml`:

```toml title="pyproject.toml"
[tool.zenzic]
excluded_assets = ["assets/social/*.svg"]
```

---

## See Also

- [Material for MkDocs: Setting up social cards](https://squidfunk.github.io/mkdocs-material/setup/setting-up-social-cards/) — the real setup mechanics
- [Why Zenzic](../explanation/why-zenzic.md)
