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

**Step 2 — write `.zenzic-vsm.json`**. What it must contain is generator-neutral: a map from
**source path relative to `docs_dir`** to the **URL that source publishes at, written the way
an author writes it in a link**. That contract does not change between generators. The script
that produces it does, materially — so pick your generator below rather than adapting the
other one.

```json
{
  "index.mdx":         { "url": "/",                "status": "REACHABLE" },
  "guides/example.md": { "url": "/guides/example/", "status": "REACHABLE" }
}
```

Nothing ships to generate this file. Writing it is the cost of this approach.

=== "Astro / Starlight"

    The build tree *is* the manifest: every `dist/**/index.html` is a published URL, and the
    source that produced it has the corresponding path under the content directory.

    ```python
    urls = {"/" if (r := h.parent.relative_to("dist").as_posix()) == "." else f"/{r}/"
            for h in Path("dist").rglob("index.html")}
    ```

    Starlight publishes docs at the site root, so source path and URL correspond directly
    and there is no prefix to handle.

=== "Docusaurus"

    **Do not derive URLs from filenames** — a page carrying `slug:` publishes somewhere its
    filename does not predict, and a filename-derived script drops it from the manifest
    silently. Docusaurus emits the pairing itself: every object under `.docusaurus/**/*.json`
    carrying both `source` and `permalink` is one route, with `slug` already resolved.

    ```python
    vsm[d["source"].replace("@site/", "")] = {"url": d["permalink"].rstrip("/") + "/",
                                              "status": "REACHABLE"}
    ```

    Two conventions must be handled or the manifest is wrong:

    - **`baseUrl`** — permalinks carry it (`/myproject/docs/intro/`) while authors write
      links without it (`/docs/intro`). Strip the prefix; otherwise every link fails.
    - **`routeBasePath`** — docs publish under `/docs/`. Set `docs_dir = "."` and exclude
      `node_modules`, `build` and `.docusaurus`, so Zenzic's own path mapping agrees with the
      published prefix. Without this the **absolute** links pass and the **relative** ones
      fail, because relative targets are mapped without the prefix.

**Step 3 — declare the engine and allow the route prefix**:

```toml
# Astro / Starlight
docs_dir = "src/content/docs"
absolute_path_allowlist = ["/"]

[build_context]
engine = "prebuilt"
```

```toml
# Docusaurus — docs_dir is the repository root, so path mapping matches routeBasePath
docs_dir = "."
absolute_path_allowlist = ["/"]
excluded_dirs = ["node_modules", "build", ".docusaurus", "src", "static"]

[build_context]
engine = "prebuilt"
```

`absolute_path_allowlist` is what silences `Z105`; without it the absolute paths are still
reported as a governance finding even once they resolve.

!!! success "Measured on real scaffolded builds of both generators"
    | Site | `standalone` | `prebuilt` + allowlist |
    | :--- | ---: | ---: |
    | Astro Starlight, 2 valid absolute links + 1 broken | 4 errors (3 `Z105` incl. **both valid links**, 1 `Z101`) | **1** — the broken link |
    | Docusaurus classic, same three links | 8 errors (3 `Z101` incl. both valid, 4 `Z105`) | **1** `Z101` — the broken link (plus one unrelated `Z516` in Docusaurus's own scaffold) |

!!! warning "Not verified: versioned docs and i18n"
    Docusaurus's **versioned docs** (`versioned_docs/version-1.0/` → `/docs/1.0/`) and
    **i18n locale prefixes** were not exercised — a scaffolded site contains neither, and
    testing them needs `docusaurus docs:version` and a configured locale set with a
    per-locale build. Both emit `permalink` through the same plugin metadata, so the script
    above is expected to carry them, but that is an expectation and not a measurement. If
    you use either, check the generated manifest against your build before trusting a green
    run.

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
