<!--
SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
SPDX-License-Identifier: Apache-2.0
-->

<p align="center">
  <a href="https://github.com/PythonWoods/zenzic">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="./docs/assets/brand/svg/zenzic-logo-dark.svg">
      <source media="(prefers-color-scheme: light)" srcset="./docs/assets/brand/svg/zenzic-logo.svg">
      <img alt="Zenzic Documentation Quality Platform" src="./docs/assets/brand/svg/zenzic-logo-dark.svg" width="480">
    </picture>
  </a>
</p>

<p align="center">
  <a href="https://github.com/PythonWoods/zenzic/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/PythonWoods/zenzic/ci.yml?branch=main&label=ci&style=flat-square" alt="ci-status">
  </a>
  <!-- zenzic:audit-badge -->
  <img src="https://img.shields.io/badge/%F0%9F%9B%A1%EF%B8%8F_zenzic--audit-passing-22c55e?style=flat-square" alt="zenzic-audit">
  <!-- zenzic:score-badge -->
  <img src="https://img.shields.io/badge/%F0%9F%9B%A1%EF%B8%8F_zenzic--score-98_%2F_100-f59e0b?style=flat-square" alt="zenzic-score">
  <a href="https://reuse.software/">
    <img src="https://img.shields.io/badge/REUSE-3.x%20compliant-0d9488?style=flat-square" alt="REUSE 3.x compliant">
  </a>
  <a href="https://pypi.org/project/zenzic/">
    <img src="https://img.shields.io/pypi/v/zenzic?label=PyPI&color=38bdf8&style=flat-square" alt="PyPI Version">
  </a>
  <a href="https://pepy.tech/project/zenzic">
    <img src="https://img.shields.io/pepy/dt/zenzic?color=4f46e5&label=downloads&style=flat-square" alt="Downloads">
  </a>
  <a href="https://pypi.org/project/zenzic/">
    <img src="https://img.shields.io/pypi/pyversions/zenzic?color=10b981&style=flat-square" alt="Python Versions">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-Apache--2.0-0d9488?style=flat-square" alt="License">
  </a>
</p>

<p align="center">
  <strong>Formatters handle syntax. Prose linters handle grammar. Zenzic protects the graph—and optionally enforces lightweight editorial policy without a separate tool.</strong><br>
  <em>A quality gate for documentation repositories — checked the same way locally, in your editor, and in CI.</em>
</p>

Zenzic scans Markdown/MDX documentation repositories for broken links, orphan pages, missing assets, leaked credentials, and structural defects, then fails the build before they ship — credential and path-traversal findings exit non-zero unconditionally, with no suppression option.

---

## Why Zenzic, Not Just a Linter

AI-assisted edits and fast-moving docs-as-code repos produce Markdown that reads clean and parses without error while quietly breaking things no single-file checker can see: a link to a page that no longer exists, a table missing a column a spec requires, a credential pasted into a fenced code block. Syntax formatters and prose linters both operate one file at a time and stop at whitespace, spelling, and grammar — neither builds a graph of the repository, so neither catches this class of defect.

| Capability | Syntax Formatters & Linters | Prose & Grammar Checkers | Zenzic |
| :--- | :--- | :--- | :--- |
| **Scope of Analysis** | Single-file syntax & whitespace | Single-file grammar & spelling | Global document graph & cross-file structure |
| **Specification Validation** | None | None | AST table structure (`Z521`), cell enums (`Z522`), heading sequence (`Z523`) |
| **Graph Traceability** | None | None | Cross-namespace reference coverage (`Z412`) & reachability (`Z410`, `Z411`) |
| **Link & Anchor Resolution** | None | None | Cross-file & framework slug parity |
| **Security Verification** | None | None | Secret leak & path traversal guards (exit codes 2 & 3) |
| **Technical Debt Management** | Inline comments only | Config ignores | Cryptographic baselines (`.zenzic-baseline.json`) & quality scoring |
| **Enterprise Governance** | None | Style rules | Policy-as-Code schemas, domain allowlists, suppression budgeting |

- **Runs alongside them, not instead of them**: Zenzic is typically paired with a formatter and a prose linter in the same pipeline. It isn't trying to replace either — it covers what's left over: the graph, the specification, and the security surface.

---

## Quick Start

Full guide: [zenzic.dev/how-to/install](https://zenzic.dev/how-to/install/). Pick the track that fits your workflow — pre-commit is the recommended default; the other two exist for locked dependency pinning and one-off audits.

**Pre-commit (recommended)** — catches broken links and leaked secrets before they're committed, no environment setup required:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/PythonWoods/zenzic
    rev: v0.30.0
    hooks:
      - id: zenzic-guard   # fast staged-file credential scan
      - id: zenzic-verify  # full documentation integrity gate
```

**Project dependency** — pin it like any other dev dependency:

```toml
# pyproject.toml
[project.optional-dependencies]
docs = ["zenzic~=0.30.0"]
```

**One-off audit** — no install, run once against any repository:

```bash
uvx zenzic@0.30.0 check all
```

Then, locally:

```bash
zenzic init         # scaffold .zenzic.toml
zenzic check all    # run the full graph analysis
zenzic fix --apply  # apply safe, idempotent auto-fixes (--dry-run to preview)
```

---

## What It Looks Like

A failing run in CI (`zenzic check all docs`, on a 4-file fixture, exit code 2 — a real capture, ASCII glyphs as rendered in an Actions log):

```text
✘ SECURITY BREACH DETECTED  [LIKELY PLACEHOLDER]
  x Finding:    Secret detected (aws-access-key) — rotate immediately.
  x Location:   docs/deploy.md:4
  x Credential:  AKIA************MPLE
  Action: Rotate this credential immediately and purge it from the repository history.

mkdocs - ./docs/ - 4 files (2 pages, 1 config, 1 assets) - 0.0s - 177 files/s

docs/assets/unused.png  !  [Z405]  File not referenced in any documentation page.
docs/deploy.md:1  !  [Z410]  Document is isolated and unreachable from defined entry points: '/deploy/'
docs/index.md:3  x  [Z101]  './setup.md' resolves to '/setup/' which is not in the Virtual Site Map
    3  ❱  See the [setup guide](./setup.md) for details.
docs/index.md:5  x  [Z104]  './assets/diagram.png' not found in docs
    5  ❱  ![architecture](./assets/diagram.png)
       │  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Summary:  x 1 security breach  - 1 file impacted  x 2 errors  ! 5 warnings  i 0 info  - 3 files with findings
FAILED: Security breaches detected. Exit code 2 is mandatory.
DQS Final Score: 0/100 (Security Override — 1 non-suppressible finding detected)
```

Credential leaks and path traversal (exit 2 / 3, see [Exit Codes](#exit-codes)) force the score to 0 and cannot be suppressed by policy or inline comment, regardless of everything else in the repo. A clean run, on this repository's own 297-file docs tree, looks like this instead:

```text
mkdocs - ./docs/ - 297 files (265 pages, 4 config, 28 assets) - 5.9s - 50 files/s
* Analysis complete: Links, credentials, semantic structure, and policies verified.
DQS Final Score: 98/100 (Gate Passed)
```

---

## Core Capabilities

- **Graph analysis** — an in-memory link/anchor/asset graph (the "Virtual Site Map," or VSM) built once per run and reused for every check: broken links (`Z101`), missing files (`Z104`), unused assets (`Z405`), and pages unreachable from any entry point (`Z410`, `Z411`). It scales linearly with repository size — doubling the page count roughly doubles scan time, not worse.
- **Security scanning** — leaked API keys and cloud credentials (`Z201` and related codes) and path-traversal sequences are exit-2 / exit-3 failures that cannot be suppressed, by design.
- **Structural specification checks** — required table columns, closed cell-value enums, and mandated heading sequences (`Z521`, `Z522`, `Z523`, `Z412`) catch AI-edited tables and specs that parse fine but violate a project's own declared contract.
- **Atomic auto-fix** (`zenzic fix`) — lossless, idempotent AST mutations: wraps bare URLs, strips trailing heading punctuation, converts fake bullet-point paragraphs into real lists, tags unlabelled code fences, cleans up dead inline suppressions, and repairs relative links across the tree after a rename (`zenzic fix --rename OLD NEW`). Running it twice never produces a second diff.
- **Quality score (DQS)** — a deterministic 0–100 score built from active findings, category weights, and suppression debt (every inline `<!-- zenzic:ignore ZXXX -->` costs a flat, capped point penalty). Gate CI on it with `fail_under` in `.zenzic.toml`; inspect the full deduction ledger with `zenzic score --breakdown`.
- **Policy-as-Code** — declared once in `.zenzic.toml` and enforced identically everywhere Zenzic runs:

  ```toml
  [policies]
  required_frontmatter_keys = ["title", "description"]
  allowed_external_domains = ["github.com", "zenzic.dev"]
  enable_passive_voice_check = true
  weasel_words = ["clearly", "simply", "obviously"]
  ```

  The last two options (`Z518` passive voice, `Z519` weasel words) are opt-in, non-backtracking RE2 pattern heuristics, not full grammar or NLP analysis — they flag likely candidates for a human to confirm, not certainties.
- **Custom rules** — the [Custom Rule SDK](https://zenzic.dev/developers/how-to/write-ast-rule/) lets teams write their own typed Python AST checks, with SARIF output for free.

---

## Architecture, Briefly

Markdown is parsed once into a lossless AST. A single linear pass builds the link/asset graph and runs every check against it; `zenzic fix` mutates that same tree and re-serializes it byte-for-byte outside the changed nodes. Analysis runs entirely in-process — no shell exec, no network calls — and all pattern matching goes through a non-backtracking regex engine (Google RE2), so a large or adversarial document can't hang the scan.

Full internals — the AST/mutator design, the scoring model, and the adapter contracts: [zenzic.dev](https://zenzic.dev).

---

## CLI Commands

| Command | Primary Use Case | Key Options |
| :--- | :--- | :--- |
| `zenzic check` | Run graph integrity, security, and quality analysis | `all`, `--strict`, `--fail-under <N>`, `--format sarif` |
| `zenzic fix` | Automatically apply idempotent AST mutations | `--dry-run`, `--apply`, `--rename OLD NEW` |
| `zenzic score` | Calculate quality metrics and update status badges | `--stamp`, `--check-stamp`, `--badge-json` |
| `zenzic audit` | Generate formal compliance and technical debt reports | `--format markdown`, `--output <file>` |
| `zenzic lab` | Interactive finding lab and scenario runner | `<code>` (e.g. `z101`), `all`, `--list`, `--all` |
| `zenzic init` | Scaffold `.zenzic.toml` configuration or plugin template | `--pyproject`, `--local`, `--engine <name>`, `--plugin` |
| `zenzic config explain` | Introspect active policies, discovery paths, and rules | `--all`, `--json` |
| `zenzic doctor` | Check repository conventions: ADR citations, redirects, config schema | `--format json`, `--quiet` |
| `zenzic adr new` | Scaffold the next architectural decision record | `<title>`, `--path` |

---

## SARIF Output for CI/CD

```bash
zenzic check all --format sarif --output results.sarif
```

Standard SARIF v2.1.0: 1-indexed line/column ranges, a quality category and point penalty on every result, and a `helpUri` linking straight to that finding's [docs page](https://zenzic.dev/reference/finding-codes/). Feeds directly into GitHub Code Scanning, SonarQube, GitLab Security Dashboards, or DefectDojo.

---

## Framework Adapters

Documentation frameworks slugify anchors and resolve asset paths differently, so Zenzic ships adapters rather than assuming one convention:

- **MkDocs & Material for MkDocs** — parses `mkdocs.yml` and the nav tree, matches Material's anchor slugification, without invoking the Python build.
- **Zensical** — validates multi-language document hierarchies and configuration trees.
- **Standalone Markdown** — universal link/asset resolution for any directory structure, no build framework required.

Tested versions and verification method per adapter: [Compatibility Matrix](https://zenzic.dev/reference/compatibility/).

---

## Exit Codes

Stable across the CLI, pre-commit hooks, and CI — script against them directly:

| Exit Code | Meaning | CI Behavior |
| :--- | :--- | :--- |
| **`0`** | Success | All checks passed, or warnings within the suppression budget. |
| **`1`** | Quality gate failure | Broken links, structural defects, or score below `fail_under`. |
| **`2`** | Credential leak | Leaked secret or API key. Never suppressible. |
| **`3`** | Path traversal | Directory traversal sequence detected. Never suppressible. |

---

## The Zenzic Ecosystem

The same rule engine and finding codes run across every touchpoint, with one tracked exception — see [Known Limitations](CHANGELOG.md#unreleased):

| Platform | Primary Use Case | Delivery |
| :--- | :--- | :--- |
| **[Zenzic CLI (Core)](https://github.com/PythonWoods/zenzic)** | Local development, batch auto-fixes, scriptable audits | Pre-commit / PyPI (`uv`/`pip`) |
| **[VS Code Extension][zenzic-vscode]** | Real-time diagnostics, LSP Quick Fixes (`Ctrl+.`), status telemetry | [VS Code Marketplace][zenzic-vscode] |
| **[GitHub Action][zenzic-action]** | CI/CD pull request gate, SARIF Code Scanning alerts, merge blocking | [GitHub Marketplace][zenzic-action] |
| **[MCP Server][zenzic-mcp]** | Exposes a single `check_document` tool to MCP-capable LLM agents over stdio | Source only — pre-release |

> **`zenzic-mcp` is pre-release.** Version `0.1.0`, no published release, and one tool —
> `check_document`, which checks a single Markdown file and returns its findings. Its
> interface may change without a deprecation period until a `1.0.0` exists.

---

## Documentation & Guides

- **[Quick Start Tutorial](https://zenzic.dev/tutorials/first-audit/)**: Step-by-step introduction.
- **[Finding Codes Catalog](https://zenzic.dev/reference/finding-codes/)**: Complete reference for all `Z1xx`–`Z6xx` finding codes.
- **[Policy-as-Code Guide](https://zenzic.dev/how-to/configuration-strategy/)**: Enforce repository standards.
- **[Custom Rule SDK](https://zenzic.dev/developers/how-to/write-ast-rule/)**: Author deterministic, typed Python linting plugins.
- **[CI/CD Configuration](https://zenzic.dev/how-to/configure-ci-cd/)**: Set up automated GitHub Actions pipelines.

For deep architectural explanations, configuration strategies, and the full finding taxonomy, visit [zenzic.dev](https://zenzic.dev).

---

## Roadmap

- **Sphinx Adapter**: Native Virtual Site Map adapter for Sphinx, parsing `conf.py` and `.rst` files without invoking `sphinx-build`. Docusaurus and Hugo support is community-contributed via the [adapter guide](https://zenzic.dev/developers/how-to/implement-adapter/) — see [GH #50](https://github.com/PythonWoods-Dev/zenzic/issues/50) and [GH #51](https://github.com/PythonWoods-Dev/zenzic/issues/51).
- **Multi-Repository Documentation Graph**: Cross-repository link resolution and contract validation across polyrepo documentation architectures without network calls.
- **Auto-Fix Expansion**: Extended lossless AST mutations for additional structural codes (`Z1xx`), reference normalization (`Z3xx`), and frontmatter standardization (`Z6xx`).

---

## License

Licensed under the [Apache License, Version 2.0](LICENSE).
Copyright (c) 2026 PythonWoods `<dev@pythonwoods.dev>`.

<!-- Link Definitions -->
[zenzic-vscode]: https://github.com/PythonWoods/zenzic-vscode
[zenzic-action]: https://github.com/PythonWoods/zenzic-action
[zenzic-mcp]: https://github.com/PythonWoods-Dev/zenzic-mcp
