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
| Prebuilt (route manifest) | — | Reads `.zenzic-vsm.json`, a schema this project defines; there is no third-party version to track. What is tracked is the *generators it serves*, below | — |
| ↳ Astro / Starlight | — | `github.com/withastro/docs` pinned at `16fe0736`, re-scanned by `scripts/external_corpus_check.py`, which fails when the finding counts move. Astro is not a dependency; the pin is the version | 2026-09-19 |
| ↳ Docusaurus | — | A `create-docusaurus` classic scaffold, walked by hand through `zenzic init` and `check all`. Not pinned in CI — the scaffold is generated, not a repository to fetch | 2026-09-19 |

**What "verified" does not mean here**: there is no dedicated CI job that installs and tests
against multiple versions of any engine — verification is `mkdocs build --strict` succeeding
against whatever version `uv.lock` currently resolves, not a genuine multi-version matrix.

---

## Libraries Zenzic reproduces rather than imports

The matrix above answers *which generator versions were tested*. This answers a different
question: **where Zenzic reproduces another library's behaviour instead of calling it, and
which version of that library the reproduction was measured against.**

It reproduces rather than imports because the core takes no runtime dependency on a
documentation toolchain — the analyser must read a project it is not installed beside. A
reproduction is only as good as the version it was characterised against, so the version is
part of the contract.

| What is reproduced | Where | Characterised against | Verification method | Last verified |
| :--- | :--- | :--- | :--- | :--- |
| `markdown.extensions.toc`'s default `slugify` | `core/validator.py` — `slug_heading()` | `Markdown` `3.10.3` | `tests/test_replicas_match_the_original.py` imports the real `toc_slugify` and asserts equality on every run — a comparison, not a reading | 2026-09-18 |
| `pymdownx.slugs.slugify(case="lower")` | `core/validator.py` — `slug_tab_title()` | `pymdown-extensions` `11.0.1` (with `Markdown` `3.10.3`) | Same test, same shape: the real `slugify` is imported and compared. Deliberately without `importorskip` — a check that disappears with its subject is not a check | 2026-09-18 |
| CommonMark block structure (§4.5 fences, §4.6 HTML blocks, §4.2/4.3 headings) | `core/ast.py` — `BlockTracker` | CommonMark `0.31.2` | Test suites derived from the specification's own sections rather than from the cases found in the wild | 2026-09-20 |

Both slug reproductions are covered, and the versions above are the ones currently resolved
in `uv.lock` — the characterisation and the installed library agree today. **If they stop
agreeing, the parity test is what says so**, because it compares against whatever is
installed rather than against a recorded expectation.

!!! info "Two functions named `_slugify` are not on this list, deliberately"

    `core/rules.py` and `core/doctor.py` each define a `_slugify`, and neither reproduces a
    renderer. `rules.py`'s is a minimal normalisation used by `Z107` to compare a link's
    visible text against its own fragment — both sides pass through it, so it works by
    agreeing with itself; its docstring records that an earlier version of it **claimed** to
    be a renderer slug and was measured against `github-slugger` on nine real heading/anchor
    pairs, agreeing on none. `doctor.py`'s turns an ADR title into a filename. Neither needs
    a declared version, and listing them here would be the mistake that docstring corrects.

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

### The two generators have no version, and that is the point

Astro and Docusaurus appear with a dash in the version column because Zenzic
never reads their configuration and never runs their build. `prebuilt` reads a
route manifest **you** generate, so what matters is not which version produced
it but whether the manifest describes your site — and `Z115` reports it when it
stops doing so.

What is tracked instead is the artefact each claim was measured against. A
generator that has not been run against a real repository is not listed here or
anywhere else, which is why this table names two and not five.

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
