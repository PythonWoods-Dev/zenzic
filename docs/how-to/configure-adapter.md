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
