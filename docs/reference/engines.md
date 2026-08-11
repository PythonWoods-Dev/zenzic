---
sidebar_label: "Engine Guide"
description: "How Zenzic discovers and loads documentation engine adapters."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Engine Configuration Guide

Zenzic is **agnostic** — it works with MkDocs, Zensical, or a bare folder of Markdown files
without requiring any build framework to be installed. It is also **opinionated**: when you
declare an engine, you must prove it. This guide explains how to configure Zenzic for each
supported engine and what the rules are.

## Cross-ecosystem reach

Zenzic supports checking Markdown directories natively without requiring a build engine via the Standalone engine mode. Adapters for MkDocs and Zensical provide enhanced navigation and internationalisation support.

Zenzic analyses source Markdown files and configuration as plain data without invoking a build engine or importing framework code. Consequently, it validates documentation for any static site generator (SSG), regardless of the underlying generator language.

| Support level | Engine | SSG language | How |
| :--- | :--- | :--- | :--- |
| **Native** | MkDocs | Python | `MkDocsAdapter` — reads `mkdocs.yml`, resolves i18n, enforces nav |
| **Native** | Zensical | Python | `ZensicalAdapter` — reads `zensical.toml`, zero-YAML |
| **Agnostic** | Standalone | any | `StandaloneAdapter` — works on any Markdown folder; orphan check disabled |
| **Extensible** | Hugo *(example)* | Go | Third-party adapter via `zenzic.adapters` entry-point |
| **Extensible** | Jekyll *(example)* | Ruby | Third-party adapter via `zenzic.adapters` entry-point |

The "Extensible" entries are examples of what the adapter system enables — not shipped
adapters. A team maintaining Hugo or Jekyll documentation can write a third-party adapter
package and install it alongside Zenzic without any change to Zenzic itself:

```bash
# Example: third-party adapter for a hypothetical Hugo support package
uv pip install zenzic-hugo-adapter   # or: pip install zenzic-hugo-adapter
zenzic check all --engine hugo
```

This cross-language reach is a structural property, not a roadmap promise. The Adapter
protocol defines five methods; any Python package that implements them and registers under
the `zenzic.adapters` entry-point group is a valid Zenzic adapter — for any SSG.

---

## Supported Engine Versions

Zenzic ships adapters for specific major-version lines. Declaring a different engine is a configuration error: Zenzic will emit `Z000 UNSUPPORTED_ENGINE` and abort.

| Engine | Supported versions | Notes |
| :--- | :--- | :--- |
| MkDocs | `1.x` | Series frozen at `1.6.1`; no `1.7` planned. v2 is a separate project requiring a dedicated adapter |
| Zensical | `0.0.x` | Pre-release; API is volatile. Adapter is updated in lockstep |
| Standalone | — | Engine-agnostic; version is irrelevant |

Zenzic does **not** invoke the engine binary — it reads configuration files as plain data. Version constraints apply to the **config-file schema**, not to the installed engine binary. If your project runs a newer engine than listed, the adapter may still work; report an issue only if you observe an actual parse error or a false positive traceable to a schema change.

---

## Choosing an engine

The `[build_context]` section in `.zenzic.toml` tells Zenzic which engine your project uses:

```toml
# .zenzic.toml
[build_context]
engine = "mkdocs"   # or "zensical"
```

If `[build_context]` is absent entirely, Zenzic deterministically discovers the engine:

- `mkdocs.yml` present → `MkDocsAdapter`
- neither config present, no locales declared → `StandaloneAdapter` (orphan check disabled)

!!! info "CLI bridge — Signal-to-noise controls"
    Engine selection and report verbosity are independent concerns. Use
    [CLI Commands: Global flags](./cli.md#global-flags) to tune policy per run:

    1. `--strict` to elevate warnings and enforce external URL validation.
    2. `--exit-zero` for non-blocking observation runs.
    3. `--show-info` to inspect informational topology findings.
    4. `--quiet` for one-line CI/pre-commit output.

---

## MkDocs

`MkDocsAdapter` is selected when `engine = "mkdocs"`.
Unrecognised engine strings fall back to `StandaloneAdapter` — no nav awareness.
It reads `mkdocs.yml` using a permissive YAML loader that silently ignores unknown tags
(such as MkDocs `!ENV` interpolation), so environment-variable-heavy configs work without
any preprocessing.

### Static analysis limits

`MkDocsAdapter` parses `mkdocs.yml` as **static data**. It does not execute the MkDocs
build pipeline. This means:

- **`!ENV` tags** — silently treated as `null`. If your nav relies on environment variable

  interpolation at build time, the nav entries that depend on those values will be absent
  from Zenzic's view.

- **Plugin-generated nav** — plugins that mutate the nav at runtime (e.g. `mkdocs-awesome-pages`,
  `mkdocs-literate-nav`) produce a navigation tree that Zenzic never sees. Pages included
  only by these plugins will be reported as orphans.
  *Technical Note on `mkdocs-awesome-pages`: Zenzic's static adapter does not read `.pages` files. If you use `.pages` files to define navigation, Zenzic will not see those pages as reachable and will flag them as orphans unless they are explicitly linked from other reachable pages.*

- **Macros** — `mkdocs-macros-plugin` (Jinja2 templates in Markdown) is not evaluated.

  Links inside macro expressions are not validated.

For projects that rely heavily on dynamic nav generation, add the plugin-generated paths to
`excluded_dirs` in `.zenzic.toml` to suppress false orphan reports until a native adapter
is available.

### Blog plugin support (`material/blog`)

When the `blog` (or `material/blog`) plugin is enabled in `mkdocs.yml`, `MkDocsAdapter` automatically inspects `blog_dir` (default: `blog`).

All Markdown files located under `<blog_dir>/posts/` (e.g. `docs/blog/posts/*.md`) are dynamically generated routes at build time (index, pagination, tag archives, RSS). `MkDocsAdapter` marks all files in this subtree as `REACHABLE` automatically, ensuring that blog posts do not require explicit listing in `mkdocs.yml`'s `nav:` section and do not emit false-positive orphan page (`Z103`) findings.

### Minimal configuration

```toml
# .zenzic.toml
docs_dir = "docs"

[build_context]
engine         = "mkdocs"
default_locale = "en"
locales        = ["it", "fr"]   # non-default locale directory names (folder mode)
```

When `locales` is empty, Zenzic falls back to reading locale information directly from the
`i18n` plugin block in `mkdocs.yml` — zero configuration required for most
projects. This covers both the community `mkdocs-static-i18n` package and the
bundled i18n plugin in `mkdocs-material`, since both declare themselves as `i18n:` in `mkdocs.yml`.

### i18n: Folder Mode

In Folder Mode (`docs_structure: folder`), each non-default locale lives in a top-level
directory under `docs/`:

```text
docs/
  index.md          ← default locale
  assets/
    logo.png        ← shared asset
  it/
    index.md        ← Italian translation
```

Zenzic reads the `languages` list from `mkdocs.yml` to identify locale directories. Files
whose first path component is a locale directory are excluded from the orphan check — they
inherit their nav membership from the default-locale original.

When `fallback_to_default: true` is set, asset links from `docs/it/index.md` that resolve
to `docs/it/assets/logo.png` (absent) are automatically re-checked against `docs/assets/logo.png`,
mirroring the build engine's actual fallback behaviour. This intentionally prevents false-positive broken-link errors when the translated site correctly relies on base-language images.

```yaml title="mkdocs.yml"
# mkdocs.yml
plugins:

  - i18n:

      docs_structure: folder
      fallback_to_default: true
      languages:

        - locale: en

          default: true
          build: true

        - locale: it

          build: true
```

> **Rule:** If `fallback_to_default: true` is set, at least one language entry must have
> `default: true`. If none does, Zenzic raises `ConfigurationError` immediately — it cannot
> determine the fallback target locale.

### i18n: Suffix Mode

In Suffix Mode (`docs_structure: suffix`), translated files are siblings of the originals:

```text
docs/
  guide.md        ← default locale
  guide.it.md     ← Italian translation (same directory depth)
  assets/
    logo.png      ← same relative path from both files
```

Zenzic reads the non-default locale codes from `mkdocs.yml` and generates `*.{locale}.md`
exclusion patterns (e.g. `*.it.md`, `*.fr.md`). These files are excluded from the orphan check.

Only valid ISO 639-1 two-letter lowercase codes produce exclusion patterns. Version tags
(`v1`, `v2`), build tags (`beta`, `rc1`), three-letter codes, and BCP 47 region codes are
silently rejected — they do not produce false exclusions.

### Route URL resolution

MkDocs builds URLs from source paths when `use_directory_urls: true` (the default):
`docs/guide/install.md` → `/guide/install/`. Zenzic validates **source-level relative links**,
not built URLs — so inter-document links are identical in both routing modes.

If `use_directory_urls: false` is set, MkDocs generates flat `.html` files. Zenzic's link
validation is unaffected: relative `../api.md` links resolve correctly regardless of this
setting. Only absolute links (`/guide/`) are always flagged as `Z105 ABSOLUTE_PATH`.

---

## Zensical

`ZensicalAdapter` is selected when `engine = "zensical"`. It reads `zensical.toml` natively
using Python's `tomllib` — **zero YAML**. No `mkdocs.yml` is read or required.

### Native Enforcement

```toml
# .zenzic.toml
[build_context]
engine = "zensical"
```

### Transparent Proxy (Migration Bridge) {#zensical-transparent-proxy}

The Transparent Proxy is Zensical's signature migration feature: if `zensical.toml` is
**absent** but `mkdocs.yml` is present in the project root, `ZensicalAdapter` automatically
reads the MkDocs configuration as a bridge — no manual configuration required.

This means you can adopt Zenzic with the Zensical engine on **day one of migration**, before
writing a single line of `zensical.toml`. When the bridge activates, Zenzic banner
notifies you:

```text
NOTICE: Zensical engine active via mkdocs.yml compatibility bridge.
```

**What the bridge reads from `mkdocs.yml`:**

| MkDocs field | Used by Zensical Adapter for |
| :--- | :--- |
| `docs_dir` | Source directory discovery |
| `nav` | Nav membership (orphan detection) |
| `plugins.i18n.languages` | Locale directory identification |
| `theme.favicon`, `theme.logo` | Z404 asset guard |

!!! tip "Migration strategy"
    Use the Transparent Proxy to run `zenzic check all` on your MkDocs project *before* committing
    to Zensical. Once you are satisfied with the results, create a native `zensical.toml` for full
    parity and unlock Zensical-specific features.

### zensical.toml nav format

Zenzic reads the `[nav]` section to determine which pages are declared:

```toml
# zensical.toml
[project]
site_name = "My Docs"

[nav]
nav = [
  {title = "Home",     file = "index.md"},
  {title = "Tutorial", file = "tutorial.md"},
  {title = "API",      file = "reference/api.md"},
]
```

Files listed under `file` (relative to `docs/`) are the nav set. Any `.md` file under `docs/`
that is not in this set and is not a locale mirror is reported as an orphan.

### Why Zensical eliminates i18n complexity

> See [Configuration Loading — Agnostic Citizen chain](../explanation/configuration-loading.md) for the architectural rationale behind Zensical's native i18n versus MkDocs plugin indirection.

### Limitations

- **Plugin-generated nav** — Zensical plugins that mutate the nav at runtime are not evaluated.

  Pages included only by such plugins may be reported as orphans. Add their paths to
  `excluded_dirs` in `.zenzic.toml` to suppress false reports.

- **Dynamic content** — `zensical.toml` is parsed as static TOML. Template expressions or

  computed fields are not evaluated.

- **Discovery scope** — `ZensicalAdapter` searches for `zensical.toml` (or the MkDocs bridge)

  in the project root only. Nested workspace layouts require an explicit `docs_dir` in `.zenzic.toml`.

---

---

## Absolute Link Prohibition

**This rule applies to every engine, unconditionally.**

Links that begin with `/` are a hard error in all engine modes:

```markdown
<!-- Rejected — absolute path breaks portability -->
[Download](/assets/guide.pdf)

<!-- Correct — relative path survives any hosting prefix -->
[Download](/assets/guide.pdf)
```

A link to `/assets/guide.pdf` presupposes the site is served from the domain root. When
documentation is hosted at `https://example.com/docs/`, the browser resolves
`/assets/guide.pdf` to `https://example.com/assets/guide.pdf` — a 404. The fix is always
a relative path.

The check runs before any adapter logic — before nav parsing, before locale detection,
before path resolution. It cannot be suppressed by engine configuration.

External URLs (`https://...`, `http://...`) are not affected.

---

## Standalone (no engine)

`StandaloneAdapter` is returned when no engine config file is present and no locales are
declared. It is Zenzic's universal mode — compatible with any Markdown-based project that
does not use a supported SSG.

### When to use Standalone

- **Static Markdown repositories** — wikis, ADR logs, plain-text documentation with no

  build pipeline.

- **Pre-migration validation** — run Zenzic on a project before choosing an SSG to catch

  broken links and credentials before a framework is introduced.

- **Custom SSG projects** — any generator not yet covered by a native adapter. Use

  `excluded_dirs` to suppress false positives for generated output directories.

### Minimal configuration

```toml
# .zenzic.toml — minimum required for standalone
docs_dir = "docs"
```

No `[build_context]` section is needed. Zenzic detects the absence of engine config files
and selects `StandaloneAdapter` automatically.

### Capabilities

Snippet, placeholder, link, and asset checks run at full strength. Z201 credential detection,
Z202/Z203 path traversal detection, and Z401 logo/favicon guards all operate normally.

All adapter methods are no-ops:

- `is_locale_dir` → always `False`
- `resolve_asset` → always `None`
- `is_shadow_of_nav_page` → always `False`
- `get_nav_paths` → `frozenset()`
- `get_ignored_patterns` → `set()`

### Limitations

`find_orphans` returns `[]` immediately — without a declared nav, there is no reference set
to compare against. Orphan detection requires a nav declaration: MkDocs `nav:` or Zensical `[nav]`.

For locale-aware projects without a supported engine, add locale directory names to
`excluded_dirs` in `.zenzic.toml` to prevent false orphan reports.
