---
description: "Why Zenzic lints the source, not the build — the architecture that makes engine migrations provably safe."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Engine Migration Design

> For the step-by-step operational playbook, see [Migrating Engines](../how-to/migrate-engines.md).

---

## Your source files outlive your build engine

Build engines evolve. They change configuration formats, drop plugin systems, merge with
commercial platforms, or simply stop being maintained. When that happens, the assets at risk
are not your Markdown files — those are plain text and will always be readable. What is at
risk is your **investment in structure**: the navigation, the i18n conventions, the link
graph, the asset organisation you have built over years.

Zenzic's role in a migration is not to make the switch faster. It is to make the switch
**provably safe** — by guaranteeing that every structural invariant you care about is
measured before, during, and after the move, and that any regression is visible immediately
and attributed precisely.

This guarantee rests on a single architectural principle: **Zenzic lints the source, never
the build**. It reads `mkdocs.yml`, `zensical.toml`, and your Markdown files as plain data.
It never imports or executes a build framework. This means:

- Zenzic understands your documentation structure even if the build binary that used to interpret it no longer works.
- Running `zenzic check all` on a project in the middle of a migration produces the same analysis as on a fully operational project — because the source files have not changed.
- Switching `engine` in `.zenzic.toml` (one line) is all it takes to validate whether your content is structurally compatible with a new engine, without touching a single Markdown file.

This is the Exclusion Zone: **a fixed validation layer that remains valid before, during, and
after any build engine change**.

---

## The MkDocsAdapter: plain-data preservation

The `MkDocsAdapter` treats `mkdocs.yml` as a pure data structure — a set of nav paths,
plugin declarations, and locale settings. It extracts what it needs (nav tree, i18n
configuration, plugin flags like `reconfigure_material`) and hands the result to the Rule
Engine as typed Python objects. It never calls `mkdocs build`, never imports `mkdocs`, and
never depends on any plugin being installed or functional.

The practical consequence is that `MkDocsAdapter` preserves the MkDocs 1.x structural
contract as a versioned, static specification. As long as your `mkdocs.yml` describes a valid
MkDocs 1.x-style structure, Zenzic will understand and validate it — regardless of what any
build binary does or does not support. Running `zenzic check all` with `engine = "mkdocs"`
tests your content against that documented contract, not against any particular binary version.

This makes Zenzic's output a portable quality certificate: if Zenzic says your
documentation is structurally sound, that claim is true independently of which engine you
use to render it tomorrow.

### MkDocs 2.0 resilience model

If MkDocs 2.0 ships tomorrow with breaking changes, a Zenzic user still keeps a stable
quality gate for existing MkDocs 1.x sources.

Why this holds technically:

- `MkDocsAdapter` parses `mkdocs.yml` as static data and does not import MkDocs.
- Zenzic never executes plugin code; plugin sections are read as plain config.
- Unknown YAML tags and future keys are tolerated by a permissive loader.

Result: your validation pipeline does not depend on the lifecycle of a single build
binary. You can keep linting MkDocs 1.x conventions while evaluating migration paths.

---

## i18n: validating structure independently of rendering

The MkDocs `i18n` plugin (folder-mode and suffix-mode conventions) defines a well-specified
content structure: locale directories, fallback chains, per-locale nav shadowing. Zenzic
encodes this specification in `MkDocsAdapter` and the Virtual Site Map independently of any
rendering implementation.

This matters during engine transitions. When a build engine is still maturing its i18n
support, there is a window where the *structural rules* of your i18n setup are well-defined
but the *rendering capability* of the engine may not yet be complete. Zenzic operates
entirely in the structural domain:

- **Cross-locale link resolution** — a link from an Italian page to an English-only asset is resolved against the fallback chain defined in `mkdocs.yml`, not against the build output.
- **Ghost Route detection** — locale entry points generated at build time (e.g. `/it/`) are marked `REACHABLE` in the VSM so they are never reported as orphans, even if they have never been rendered.
- **Locale directory suppression** — files under `docs/it/`, `docs/fr/`, etc. are classified as locale shadows, not orphans.

You can therefore validate a complex i18n structure with Zenzic and be confident in its
internal consistency — the link graph is correct, the fallback chains are intact, the nav
is complete — before committing to any rendering engine.
