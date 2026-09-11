---
description: "Configure adapter behavior, locale settings, and engine-specific options."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Configure Adapters and Engine

Zenzic uses an **adapter** to obtain engine-specific knowledge — nav structure, i18n directories,
and locale patterns — without importing or executing any build framework.

> For the complete `[build_context]` field reference, adapter discovery rules, and ZensicalAdapter nav format, see [Configuration Reference — `[build_context]`](../reference/configuration-reference.md#build-context). For the specific engine version each adapter is tested against, see the [Tested Compatibility Matrix](../reference/compatibility.md).

---

## Declare your engine

Add a `[build_context]` section to `.zenzic.toml` to set the engine explicitly:

```toml
[build_context]
engine         = "auto"     # "auto" (default), "mkdocs", "zensical", "standalone"
default_locale = "en"       # ISO 639-1 code of the default locale
locales        = ["it"]     # non-default locale directory names (e.g. docs/it/, docs/fr/)
```

The same section is available under `[tool.zenzic.build_context]` when embedding configuration in `pyproject.toml` instead:

```toml title="pyproject.toml"
[tool.zenzic.build_context]
engine = "mkdocs"
```

---

## `--engine` flag (one-off override)

The `--engine` flag on `zenzic check orphans`, `zenzic check all`, `zenzic clean assets`, and
`zenzic init` overrides `build_context.engine` for a single run without touching `.zenzic.toml`:

```bash
zenzic check orphans --engine zensical
zenzic check all --engine mkdocs
```

If you pass `--engine` a name that has no registered adapter, Zenzic lists the available
adapters and exits with code 1:

```text
ERROR: Unknown engine adapter 'hugo'.
Installed adapters: mkdocs, prebuilt, standalone, vsm, zensical
```

A near miss also gets a suggestion — `--engine mkdoc` adds `Did you mean mkdocs?`. An unknown
engine written into `.zenzic.toml` instead is rejected earlier, by config validation, which
reports the same set as a schema error rather than through this message.

---

## A framework Zenzic has no adapter for (Astro, Docusaurus, Next.js) {#prebuilt-route-manifest}

Zenzic ships adapters for MkDocs and Zensical. For any other generator the default
`standalone` adapter has no way to know the site's URL convention, so an **absolute** link
like `/guides/example/` cannot be resolved: `Z101` reports it as absent from the Virtual
Site Map, and `Z105` reports the absolute path itself. On a site that links by route —
which is the idiom in Astro, Docusaurus and Next.js — that is the dominant finding, and
none of it is a broken link.

`prebuilt` closes this without Zenzic learning anything about your generator. It reads
`.zenzic-vsm.json` from the repository root: a map of source path to published URL.

**Step 1 — build the site**, so the generator states its own routes:

```bash
npx astro build        # or: npm run build
```

**Step 2 — write `.zenzic-vsm.json`** from the build output. The URLs are the directories
the build emitted; pair each with the source that produced it:

```json
{
  "index.mdx":            { "url": "/",                  "status": "REACHABLE" },
  "guides/example.md":    { "url": "/guides/example/",   "status": "REACHABLE" },
  "reference/example.md": { "url": "/reference/example/", "status": "REACHABLE" }
}
```

Keys are relative to `docs_dir`. Nothing ships to generate this file — it is a short script
over the build output, and writing it is the cost of this approach.

**Step 3 — declare the engine and allow the route prefix**:

```toml
docs_dir = "src/content/docs"
absolute_path_allowlist = ["/"]

[build_context]
engine = "prebuilt"
```

`absolute_path_allowlist` is what silences `Z105`; without it the absolute paths are still
reported as a governance finding even once they resolve.

!!! success "Verified on a real Astro Starlight build"
    A scaffolded Starlight site with two valid absolute links and one broken one reports
    **four findings** under `standalone` — three `Z105` including both valid links, plus a
    `Z101`. Under `prebuilt` with the allowlist it reports **one**: the broken link. That is
    the whole difference between a gate a user can act on and one they will switch off.

---

## Engine coexistence (`mkdocs.yml` + `zensical.toml` in the same repo)

Some repositories carry both `mkdocs.yml` and `zensical.toml` during a transition — one
build test-running Zensical while the other keeps serving production on MkDocs.

When `engine` is explicitly declared in `.zenzic.toml`, Zenzic uses that adapter — even when
another engine's config file is also present. `engine = "mkdocs"` always reads `mkdocs.yml`
even if `zensical.toml` exists, and vice versa.

If `engine` is omitted (or `build_context` is absent entirely), the default is `engine = "auto"`.
Zenzic then uses Auto-Discovery: it inspects the project root for known manifests and mounts
the correct adapter automatically.

!!! info "Auto-Discovery priority order"
    1. `.zenzic-vsm.json` → prebuilt VSM artifact (skips adapter discovery entirely)
    2. `zensical.toml` → `ZensicalAdapter`
    3. `mkdocs.yml` / `mkdocs.yaml` with `theme: zensical` → `ZensicalAdapter` (compat)
    4. `mkdocs.yml` / `mkdocs.yaml` → `MkDocsAdapter`
    5. No manifest found → `StandaloneAdapter`

```toml
# .zenzic.toml — explicit engine declaration required
[build_context]
engine = "zensical"   # ← this line is what activates ZensicalAdapter
```

---

## Third-party adapters

Third-party adapters (e.g. `zenzic-hugo-adapter`) are discovered automatically once installed as
Python packages — no Zenzic update required. Register via the `zenzic.adapters` entry-point group.

See [Writing an Adapter](../developers/how-to/implement-adapter.md) for the full protocol.
