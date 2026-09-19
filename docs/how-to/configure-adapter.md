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

**Step 1 — decide whether you need a build.** The two generators differ here, and the difference
is not cosmetic:

- **Docusaurus needs one.** Its routing is not derivable from filenames — a page carrying `slug:`
  publishes somewhere its path does not predict — so the manifest has to come from what the build
  emitted. Run `npm run build` first.
- **Astro / Starlight does not.** Its routing is positional, so the manifest can be derived from
  the source tree. Run `npm run build` if you want the built tree as the source of truth; the
  Astro tab below gives both.

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

    Starlight publishes docs at the site root, so on a **single-locale** site source path and
    URL correspond directly. On an i18n site they do not: `src/content/docs/<locale>/…`
    publishes under `/<locale>/…`, and that segment is part of every URL an author writes.

    !!! tip "Astro content collections need no build"

        A Starlight site routes **positionally**: `src/content/docs/<path>.mdx` publishes at
        `/<path>/`, and `index.mdx` at the directory's own URL. So the manifest can be written
        from the source tree alone, which is what makes this usable in a job that cannot run
        `astro build`:

        ```python
        # `prefix` is "/" on a single-locale site, and "/<locale>/" when the site uses i18n.
        # Getting it wrong is the one mistake that leaves the manifest resolving nothing.
        docs, prefix = Path("src/content/docs/en"), "/en/"
        routes = {}
        for p in sorted(docs.rglob("*.mdx")):
            rel = p.relative_to(docs).as_posix()
            slug = rel.removesuffix(".mdx").removesuffix("/index")
            routes[rel] = {"url": f"{prefix}{slug}/" if slug else prefix, "status": "REACHABLE"}
        ```

        The manifest **key** is the source path relative to `docs_dir`, so it does not carry
        the locale segment. The **URL** must. Getting this backwards produces a manifest that
        is complete, well-formed, and resolves nothing.

    !!! success "The two settings are not alternatives, and neither works alone"

        **Without a manifest**, internal links fail in bulk: the engine has no way to know what
        URL a source file publishes at, so every absolute link is reported as pointing at a page
        that does not exist.

        **With the manifest but without `absolute_path_allowlist`**, you are no better off — and
        on a site that links by route you may be worse. The links now resolve, and every one of
        them is still reported as a governance finding for being an absolute path.

        **With both**, the count falls by an order of magnitude and what remains is worth reading.

    **Check you got it right before trusting the result.** Run `zenzic check all` once before
    the manifest and once after, and read the *count*:

    - **It does not move at all.** `.zenzic-vsm.json` is not where Zenzic looked — it is read
      from the **repository root**, not from `docs_dir`. Declaring `engine = "prebuilt"` with no
      manifest present is not an error and produces no message: the run falls back to
      `standalone` and reports exactly what `standalone` reports. Check the file is there before
      looking for anything subtler.
    - **It moves, but nowhere near tenfold.** The manifest's URLs are not the URLs your authors
      write. On an i18n site this is almost always the missing locale prefix — the keys are
      relative to `docs_dir` and lose the segment, the URLs must keep it.
    - **It drops, but `Z105` is most of what remains.** `absolute_path_allowlist` is missing.
    - **It goes up.** The manifest covers a smaller tree than `docs_dir` does — a one-locale
      manifest pointed at every locale is the usual way in.

    A correct manifest moves the count by an order of magnitude. A small improvement is not a
    partial success here; it means the mapping is wrong and the findings that remain cannot
    be trusted either way.

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

!!! warning "MDX is not yet a surface Zenzic reports accurately, and this recipe cannot change that"
    Configuring the adapter correctly makes the count drop by an order of magnitude, and what
    survives is still not trustworthy on an MDX site. Zenzic reads Markdown; MDX adds constructs
    it does not model, and the result is findings that are **wrong**, not merely noisy:

    | Code | What it reports | Why it is wrong on MDX |
    | :--- | :--- | :--- |
    | `Z520` | A malformed list | The `import … from '…';` block every MDX file opens with |
    | `Z403` | An image with no alt text | The image is inside a fenced code block |
    | `Z515` | A bare URL in prose | The URL is an attribute of a JSX element written across more than one line |
    | `Z107` | A self-referential anchor | An ordinary cross-reference whose link text matches the heading it points at |
    | `Z301`, `Z108` | An undefined or empty link reference | `[][]` inside an HTML `<code>` element is a type, not a link |

    Measured on a large public Starlight site after correct configuration, these accounted for
    **about three findings in five**. Two further codes are not defects but still will not match
    your site: `Z102` predicts anchors the way Python-Markdown does, and Astro and Docusaurus both
    slugify differently; `Z503` parses fences labelled `json` as strict JSON, and much real-world
    configuration in them is JSON5.

    **There is no subset of codes that is currently clean on MDX**, so this page does not offer a
    `--only` list that would imply one. Use Zenzic on an MDX site to read findings by hand, not to
    gate a pipeline, until these close. They are tracked as engine defects, and this warning will
    be removed by the release that fixes them rather than by a reassurance.

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
