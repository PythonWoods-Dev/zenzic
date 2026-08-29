---
description: "How to switch your documentation build engine from MkDocs to Zensical with Zenzic as a safety net."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Migrating to Zensical

!!! note "Zenzic vs Zensical"
    **Zenzic** is the document integrity engine described in this documentation site — the tool
    you run with `zenzic check all`.

    **Zensical** is a separate build engine (a compatible successor to MkDocs 1.x). This page
    describes how to use Zenzic as a safety net while switching your *build engine* from MkDocs
    to Zensical.

    You do not need to use Zensical to use Zenzic. Zenzic works with MkDocs, Zensical,
    standalone Markdown folders, and any engine that has an adapter.

---

> For the architectural rationale behind this approach — why Zenzic lints the source and not the build, how the MkDocsAdapter preserves the structural contract, and how i18n is validated independently of rendering — see [Engine Migration Design](../explanation/engine-migration-design.md).

---

## What stays the same when switching to Zensical

Zensical reads `mkdocs.yml` natively. Many projects can switch the build binary without
touching a single documentation file. From Zenzic's perspective:

- The `docs/` directory layout is unchanged.
- `mkdocs.yml` remains valid as the primary navigation and configuration source; Zensical

  reads it directly.

- i18n folder-mode and suffix-mode conventions are structurally identical.
- `[build_context]` in `.zenzic.toml` can stay as `engine = "mkdocs"` until you are ready

  to create `zensical.toml`.

---

## MkDocs Material i18n integration

Zensical does not use the `mkdocs-static-i18n` plugin (see [What stays the same](#what-stays-the-same-when-switching-to-zensical) above) — this section applies only while you are still on the MkDocs engine.

### Language switcher configuration

When using `mkdocs-material` with the `i18n` plugin (`mkdocs-static-i18n`) and multiple
locales, the plugin can auto-configure the Material theme's language switcher for you via
its own `reconfigure_material` option — Zenzic does not configure or validate this switcher.
See the plugin's own
[Setting up mkdocs-material](https://ultrabug.github.io/mkdocs-static-i18n/setup/setting-up-material/)
documentation for how to enable and control it, and how it interacts with a manually
declared `extra.alternate` block.

**Why Zenzic handles this correctly:**
When `reconfigure_material: true` is present in `mkdocs.yml`, Zenzic recognises that the
Material theme will auto-generate locale entry points (e.g. `/it/`) at build time. These
pages are never listed in `nav:` — they are synthetic routes produced by the plugin. Zenzic
marks them as **auto-generated REACHABLE** in the Virtual Site Map so they are never
reported as orphans.

---

## Migration playbook

!!! info "CLI bridge — Global flags"
    Engine migration changes adapters, not Zenzic policy. Keep run behavior aligned with
    [CLI Commands: Global flags](../reference/cli.md#global-flags):

    1. `--strict` for hard-gate validation during cutover.
    2. `--exit-zero` for observation windows without breaking the pipeline.
    3. `--show-info` to inspect link-graph signals (for example `CIRCULAR_LINK`).
    4. `--quiet` for silent builders in CI hooks.

### Step 1 — Establish a baseline

Run the full check suite and lock in a quality baseline before changing anything:

```bash
# Confirm the documentation is structurally sound before touching the build layer
zenzic check all
zenzic score --save   # persist baseline to .zenzic-score.json
```

A saved baseline means that any regression introduced during the migration is immediately
measurable with `zenzic diff`. The baseline is a snapshot of your source state — it does
not depend on any build engine being functional.

### Step 2 — Switch the build binary

Install Zensical alongside (or instead of) MkDocs:

```bash
uv pip install zensical   # or: pip install zensical
```

You can now test your documentation against the Zensical engine without even creating a `zensical.toml`. `ZensicalAdapter` falls back to reading your existing `mkdocs.yml` when no `zensical.toml` is present:

```bash
zenzic check all --engine zensical
```

Zenzic will read your existing `mkdocs.yml` and validate how Zensical would interpret it.

Run the documentation build to verify it produces correct output:

```bash
uv run mkdocs build
```

Zenzic's checks are engine-neutral — run them after the build to confirm the source
structure is intact:

```bash
zenzic check all
zenzic diff              # should report zero delta against the pre-migration baseline
```

### Step 3 — Declare Zensical identity (optional)

If you want Zenzic to enforce the Zensical structural contract using `ZensicalAdapter` for nav
extraction — `zensical.toml` is not required at this point either, the adapter falls back to
`mkdocs.yml` exactly as in Step 2 — update `.zenzic.toml`:

```toml
# .zenzic.toml
[build_context]
engine = "zensical"
default_locale = "en"
locales        = ["it"]   # if you have non-default locale dirs
```

And create a minimal `zensical.toml` at the repository root:

```toml
# zensical.toml  (Zensical)
[project]
site_name = "My Documentation"
docs_dir  = "docs"
nav = [
    "index.md",
    {"Guide" = "guide.md"},
]
```

!!! tip "Flexible Identity"
    Declare `engine = "zensical"` in `.zenzic.toml` before `zensical.toml` exists. Zenzic reads
    your existing `mkdocs.yml` and validates it against the Zensical structural contract.
    Switch the engine declaration, run `zenzic check all`, see the result — no Markdown file
    touched, no pipeline broken.

    While reading `mkdocs.yml` in this fallback mode, Zenzic emits warnings for MkDocs-specific keys
    that Zensical ignores: `remote_branch`, `remote_name`, `exclude_docs`, `draft_docs`,
    `not_in_nav`, `validation`, `strict`, `hooks`, and `watch`.

### Step 4 — Verify link integrity

The link check is your most important validation step. Run it against the completed
migration:

```bash
# Internal links + i18n fallback resolution
zenzic check links

# Reference-style links + credential scanner (credential detection)
zenzic check references

# Full suite
zenzic check all
zenzic diff --threshold 0   # fail on any regression, no margin
```

If the score matches the pre-migration baseline, the migration is complete.

---

## Your migration options

Switching to Zensical is one of several paths available to a project on MkDocs. Zenzic
supports all of them with the same quality guarantee:

| Path | `engine` in `.zenzic.toml` | What Zenzic validates |
| :--- | :--- | :--- |
| Stay on MkDocs 1.x | `"mkdocs"` | Full MkDocs 1.x structural contract |
| Switch to Zensical | `"zensical"` | Zensical nav (via TOML or legacy YAML bridge) |
| Migrate to another engine | `"mkdocs"` during transition, then adapter | Source integrity throughout |
| Evaluate without committing | `--engine mkdocs` or `--engine zensical` (CLI flag) | Dry-run compatibility check |

The `--engine` CLI flag lets you run a single check against a different engine adapter
without touching `.zenzic.toml`:

```bash
# Test whether your current source is structurally compatible with Zensical
# without declaring the switch in .zenzic.toml
zenzic check all --engine zensical
```

---

## Keeping custom rules during migration

`[[custom_rules]]` in `.zenzic.toml` are **adapter-independent** — they fire identically
regardless of the engine. Any rules you had in place for your MkDocs project continue to
work without modification after switching to Zensical:

```toml
# These rules work with both engines
[[custom_rules]]
id       = "ZZ-NODRAFT"
pattern  = "(?i)\\bDRAFT\\b"
message  = "Remove DRAFT marker before publishing."
severity = "warning"

[build_context]
engine = "zensical"
```

---

## Quick reference

| Step | Command | Expected result |
| :--- | :--- | :--- |
| Baseline | `zenzic score --save` | Score saved to `.zenzic-score.json` |
| Compatibility dry-run | `zenzic check all --engine zensical` | Structural issues with Zensical adapter |
| After build switch | `zenzic check all` | Same issues as before |
| Regression check | `zenzic diff` | Delta = 0 |
| Flexible identity | `engine = "zensical"` in `.zenzic.toml` | Uses `zensical.toml` or falls back to `mkdocs.yml` |
| Final gate | `zenzic diff --threshold 0` | Exit 0 only if score did not drop |
