---
description: "Which documentation engine versions Zenzic verifies against, how, and when it was last checked."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Tested Compatibility Matrix

Zenzic does **not** invoke any documentation engine's binary — it reads configuration files
(`mkdocs.yml`, `zensical.toml`) as plain data (Zero Subprocess, [ADR 002](../developers/explanation/adr-vault/records/adr-002-zero-subprocesses.md)).
"Compatibility" here therefore means something specific: does an adapter's parsing logic match
the target engine's actual config-file and navigation schema — not "is this exact binary
installed and exercised in CI."

---

## Matrix

| Engine | Tested version | Verification method | Last verified |
| :--- | :--- | :--- | :--- |
| MkDocs | `1.6.1` (pinned `>=1.5.0,<2`) | `uv.lock`-resolved version, exercised by `mkdocs build --strict` in CI on every push (`ci.yml`, `release-docs.yml`) — this project's own docs site building cleanly, not a dedicated multi-version matrix | 2026-08-29 |
| Material for MkDocs | `9.7.7` (pinned `>=9.0.0,<10`) | Same as MkDocs above | 2026-08-29 |
| Zensical | `0.0.62` (pre-1.0) | Manual schema review against Zensical's own documentation repository (`github.com/zensical/docs` at `6346cfd`) and its published releases — Zensical is not a pip dependency of this project (nothing to lock or CI-build against; `ZensicalAdapter` parses its config as data) | 2026-09-16 |
| Standalone | — | Engine-agnostic; no external schema to track | — |

**What "verified" does not mean here**: there is no dedicated CI job that installs and tests
against multiple versions of any engine — verification is `mkdocs build --strict` succeeding
against whatever version `uv.lock` currently resolves, not a genuine multi-version matrix.

---

## Engine configuration keys: honoured, declined, unhandled

Three states, not two. A key Zenzic reads and acts on is not the same as a key it
has decided to ignore, and neither is the same as one nobody has looked at yet.

| Key | MkDocs | State in Zenzic | What that means |
| :--- | :--- | :--- | :--- |
| `nav` | supported | **Honoured** | The navigation tree drives reachability (`Z402`, `Z103`, `Z410`). |
| `docs_dir` | supported | **Honoured** | Sets the corpus root. |
| `site_dir` | supported | **Honoured** | Build output is excluded from quality analysis, never from the credential scan. |
| `not_in_nav` | supported | **Honoured** (page side) | A declared page is reachable-by-intent: no `Z402`, and no `Z103` on links into it. The page is still built and served. |
| `exclude_docs` | supported | **Honoured** | The page is absent from the built site, so it leaves quality scope entirely. Still scanned for credentials. |
| `draft_docs` | supported | **Honoured**, with build semantics | `mkdocs serve` renders a draft; `mkdocs build` omits it. Zenzic analyses a repository, not a running command, so it treats a draft as absent from the published site. |
| `validation` | supported | **Declined** | Zenzic has its own severity model; it does not defer to MkDocs' per-check log levels. |
| `strict` | supported | **Declined** | `--strict` is Zenzic's own flag, and the engine's value does not set it. |
| `hooks` | supported | **Unhandled** | Arbitrary Python that can rewrite the corpus at build time. Nothing reads it. |
| `plugins` | supported | **Partly handled** | Four families are read: `i18n` (locale trees and fallback), `material/blog` (post directories), `awesome-pages` (adds `.pages` to engine metadata), and monorepo plugins (included sub-project configs). Every other plugin is neither read nor reported. |

An unparseable pattern in any of the three `PathSpec` keys is reported as
[`Z407`](finding-codes.md#z407) rather than silently ignored — MkDocs refuses to
build on one, and Zenzic will not pretend the declaration had an effect.

**Zensical supports none of the three `PathSpec` keys.** Its own compatibility
documentation lists `not_in_nav`, `exclude_docs` and `draft_docs` under "not yet
supported", so these declarations have no effect under that engine and the
`.zenzic.toml` exemption mechanisms remain the way to express the same intent.

---

## MkDocs 2.0 is a known, real, upcoming break — not hypothetical

MkDocs 1.x has had no releases since `1.6.1` (August 2024). MkDocs 2.0 is a separate,
ground-up rewrite with confirmed backward-incompatible changes (no plugin system, no theme
override compatibility, no migration path) — Material for MkDocs's own build tooling prints
a warning about this on every `mkdocs build` run today. `pyproject.toml`'s `mkdocs>=1.5.0,<2`
and `mkdocs-material>=9.0.0,<10` pins mechanically exclude this future release — a `uv lock`
cannot silently resolve into it; upgrading past the ceiling requires an explicit, reviewed
`pyproject.toml` change.

## Zensical is pre-release and its schema may still change

Zensical is under `0.0.x` versioning — the maintainers' own convention for "pre-1.0, API not
yet stable." `ZensicalAdapter` tracks the current schema as of its last update; a Zensical
release that changes `zensical.toml` or nav-output shape may require an adapter update before
Zenzic recognizes it correctly.

---

## Related

- [Engine Configuration Guide](engines.md) — how to declare and configure an engine
- [Configure Adapters and Engine](../how-to/configure-adapter.md) — task-oriented setup guide
