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
| Zensical | `0.0.57` (pre-1.0) | Manual schema review against Zensical's own live documentation and `zensical.toml` format — Zensical is not a pip dependency of this project (nothing to lock or CI-build against; `ZensicalAdapter` parses its config as data) | 2026-08-27 |
| Standalone | — | Engine-agnostic; no external schema to track | — |

**What "verified" does not mean here**: there is no dedicated CI job that installs and tests
against multiple versions of any engine — verification is `mkdocs build --strict` succeeding
against whatever version `uv.lock` currently resolves, not a genuine multi-version matrix.

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
