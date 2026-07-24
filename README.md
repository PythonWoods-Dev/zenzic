<!--
SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
SPDX-License-Identifier: Apache-2.0
-->

<p align="center">
  <a href="https://github.com/PythonWoods/zenzic">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="assets/brand/svg/zenzic-wordmark-dark.svg">
      <source media="(prefers-color-scheme: light)" srcset="assets/brand/svg/zenzic-wordmark.svg">
      <img src="assets/brand/svg/zenzic-wordmark.svg" alt="Zenzic" width="360">
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
  <strong>Deterministic Document Integrity Engine and SAST for Markdown/MDX graphs.</strong><br>
  <em>Tiered code governance, frozen security contracts, and RE2-backed deterministic scanning.</em>
</p>

---

## ⚡ Try it now — Zero Installation

Analyzing documentation graphs? Run instant security and topological analysis using [`uv`][uv]:

```bash
uvx zenzic check all ./your-folder
```

Zenzic identifies your engine via its configuration files or defaults to **Standalone Mode**
when analyzing documentation graphs — providing immediate SAST protection for links, credentials, and
graph integrity.

---

## 🚀 Quick Start

```bash
pip install zenzic
cd my-docs-repo
zenzic init       # Establish the workspace boundary (creates .zenzic.toml)
zenzic check all  # Analyze documentation graphs in current directory
```

## 🧠 Key Capabilities

### 1. Security Scanning (SAST)

- **Z2xx Rules**: Hardened Static Application Security Testing for documentation graphs.
- **Credential Leaks (Z201)**: Hardcoded tokens, API keys, and secret patterns detected before reaching PRs.
- **Path Traversal Guard (Z202 / Z203)**: Non-suppressible filesystem boundary security checks; fatal exit codes (exits 2/3) survive `fail-on-error: false`.

### 2. Graph Topology Analysis

- **Virtual Site Map (VSM)**: Comprehensive $O(N)$ topological modeling of documentation graphs.
- **Cross-File Link Resolution**: Validates anchor boundaries and cross-document dependencies.
- **Orphan Pages & Dead Navigation**: Flags unlinked graph nodes, missing directory indices, and unreachable content.

### 3. Deterministic CI/CD Enforcement

- **Zero-DBT Quality Gate**: Bit-for-bit identical findings across all execution environments.
- **Frozen Contracts**: `FROZEN_CODES`, `NON_SUPPRESSIBLE_CODES`, and standardized SARIF output.
- **Inspect-First Workflow**: Query live code semantics with `zenzic inspect codes`.

📖 [Full docs →][docs-home] · 🏅 [Badges][docs-badges] · 🔄 [CI/CD guide][docs-cicd]

---

## ⚙️ Commands Overview

| Command | Purpose |
| :--- | :--- |
| `zenzic init` | Scaffold workspace configuration (`.zenzic.toml`) |
| `zenzic check all [PATH]` | Full documentation audit — links, credentials, orphans |
| `zenzic score [--fail-under N] [--stamp]` | Compute the Documentation Quality Score (0–100) |
| `zenzic diff [--base PATH]` | Detect debt regression against a saved baseline |
| `zenzic guard scan [PATH]` | Defense-in-Depth credential pre-gate (fatal on security findings: exit 2) |
| `zenzic inspect codes` | Query live error-code semantics and suppressibility |

---

> 🚀 **CI/CD Ready:** Use the [Official Zenzic Action](https://github.com/PythonWoods/zenzic-action) to run Zenzic in GitHub Actions — findings surface directly in Code Scanning, PR annotations, and the Security tab.
>
> ```yaml
> - uses: PythonWoods/zenzic-action@v2
>   with:
>     format: sarif
>     upload-sarif: "true"
> ```

### 📊 Headless Data Pipeline (SARIF Output)

Zenzic Core is headless and emits standardized **SARIF** (Static Analysis Results Interchange Format) JSON, ensuring seamless integration with modern CI dashboards and scanning services:

```json
{
  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "zenzic",
          "version": "0.24.2",
          "rules": [
            {
              "id": "Z101",
              "name": "BrokenLink",
              "shortDescription": { "text": "Broken documentation link" }
            }
          ]
        }
      },
      "results": [
        {
          "ruleId": "Z101",
          "level": "error",
          "message": { "text": "Broken documentation link — ./setup.md#prerequisites" },
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": { "uri": "docs/getting-started.md" },
                "region": { "startLine": 23 }
              }
            }
          ]
        }
      ]
    }
  ]
}
```

---

## 🔌 Multi-Engine Support

| Engine | Adapter | Highlights |
| :--- | :--- | :--- |
| [MkDocs][mkdocs] | `MkDocsAdapter` | i18n suffix + folder modes, `fallback_to_default` |
| [Zensical][zensical] | `ZensicalAdapter` | Transparent Proxy bridges `mkdocs.yml` |
| Any folder | `StandaloneAdapter` | File integrity checks — orphan detection disabled without a nav contract |

See the [Adapter API][docs-arch] for the plugin interface. Third-party adapters install via the `zenzic.adapters` entry-point group.

---

## 📝 IDE Integration

Zenzic provides a Language Server Protocol (LSP) backend via the `zenzic lsp` command, bringing real-time structural analysis and error reporting directly into your editor.

> **Note:** The official VS Code extension is currently in Private Beta and will be released to the Microsoft Marketplace soon.

---

## ⚙️ Configuration

Zero-config by default. See the [Configuration Guide][docs-home] for the full `.zenzic.toml` schema and `pyproject.toml` embedding.

```bash
zenzic init        # Generate .zenzic.toml with auto-detected values
```

---

## 🔄 CI/CD Integration

```yaml
- uses: PythonWoods/zenzic-action@v2
  with:
    format: sarif
    upload-sarif: "true"
```

For zero-install `uvx` integration and regression gates, see the [CI/CD guide][docs-cicd].

---

## 🧩 Ecosystem & CI Integration

### Responsibility Matrix: Core vs Action

Zenzic Core is **radically unaware** of any CI platform. It produces portable, self-contained artefacts (SARIF, JSON, text) via a stable exit-code contract. Platform-specific behaviour — GitHub Annotations, Code Scanning upload, PR decoration — is the sole responsibility of the [Zenzic Action][zenzic-action].

| Concern | Zenzic Core | [Zenzic Action][zenzic-action] |
| :--- | :---: | :---: |
| Link validation (Z1xx) | ✅ | — |
| Credential scanner (Z2xx) | ✅ | — |
| Topology / orphan detection (Z3xx–Z6xx) | ✅ | — |
| SARIF / JSON / text output | ✅ | — |
| Exit-code contract (0 / 1 / 2 / 3) | ✅ | enforced |
| GitHub Annotations (`::error::`) | — | ✅ |
| Code Scanning SARIF upload | — | ✅ |
| PR inline diff annotations | — | ✅ |
| DQS regression blocking (`zenzic diff`) | — | ✅ |
| Sovereign nightly audit (`--audit`) | — | ✅ |
| GitLab / Bitbucket / other CI adapters | — | future adapters |

> **Design law (ADR-075):** logic that maps Zenzic output to a CI platform's native format must live in the Adapter, never in the Core. Exit codes 2 and 3 propagate unchanged through every adapter — they are never remapped or suppressed.

---

## 🛡️ Why Zenzic?

### Determinism

Every Zenzic run is a pure function of its inputs. Given the same repository state and `.zenzic.toml`, the output — finding codes, severity levels, exit code, SARIF structure — is **bit-for-bit identical** across machines, platforms, and time. There are no probabilistic judgements, no sampling, and no network-dependent results injected into the analysis path.

| Property | Guarantee |
| :--- | :--- |
| Same inputs → same output | ✅ Always |
| RE2-backed regex engine | ✅ No backtracking, no catastrophic matching |
| Frozen finding codes | ✅ `FROZEN_CODES` set; never renamed or silently retired |
| Reproducible CI artefacts | ✅ Identical SARIF across runner OS and time |

### Documentation Security

Zenzic treats documentation as a **security surface**, not just a quality metric. The tiered code model enforces a hard boundary between quality findings (suppressible, exit 1) and security findings (non-suppressible, exit 2 / 3):

- **Z201 — Credential Scanner:** hardcoded tokens, API keys, and secret patterns detected before they reach a PR.
- **Z202 / Z203 — Path Traversal Guard:** filesystem boundary violations caught at the scan boundary — `fail-on-error: false` has zero effect.
- **Suppression CAP:** a configurable ceiling on the total number of active `zenzic:ignore` suppressions. Exceeding it blocks the build, preventing systematic suppression debt from accumulating silently.

### Zero Hallucinations

Zenzic reports only what is **statically verifiable** in the repository at scan time. It never:

- infers intent or "probable" correctness from surrounding context,
- approximates link validity without a deterministic check,
- emits a finding it cannot reproduce on a re-run with identical inputs.

This makes every Zenzic finding a **falsifiable, reproducible fact** — suitable as audit evidence, not just developer feedback.

---

## 📦 Installation

> 🏗️ **Monorepo Architecture**: Zenzic contains its own documentation portal. To develop locally, install the documentation toolchain with `uv sync --extra docs`.

```bash
# Zero-install, one-shot audit (recommended for CI and exploration)
uvx zenzic check all ./docs

# Global CLI tool
uv tool install zenzic

# Pinned dev dependency
uv add --dev zenzic

# pip
pip install zenzic
```

### Upgrading Zenzic

If you installed Zenzic globally via `uv`, you must explicitly request an upgrade to fetch the latest deterministic engine:

```bash
uv tool upgrade zenzic
```

To run a specific version ephemerally without altering your global environment:

```bash
uvx zenzic@0.24.2 check all
```

---

## 📖 Documentation

| Area | URL | Audience |
| :--- | :--- | :--- |
| 👤 User Guide | [zenzic.dev][docs-home] | Install, configure, CI/CD, finding codes |
| 🔧 Developer Portal | [zenzic.dev/developers][docs-developers] | Adapters, ADRs, CLI architecture, mutation testing |
| 🛡️ Security | [Engineering Ledger][docs-eng-ledger] · [SECURITY.md][security] | Security reviewer |

---

## 🤝 Contributing

1. Open an [issue][issues] to discuss the change.
2. Read the [Contributing Guide][contributing].
3. Every PR must pass `just verify` and include SPDX headers on new files.

See also: [Code of Conduct][coc] · [Security Policy][security]

## 📎 Citing

A [`CITATION.cff`][citation-cff] is present at the root. Click **"Cite this repository"** on GitHub for APA or BibTeX output.

## 📄 License

Apache-2.0 — see [LICENSE][license].

This project strictly adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

<div align="center">
  <a href="https://zenzic.dev">
    <img src="https://raw.githubusercontent.com/PythonWoods/zenzic/main/assets/brand/pythonwoods-logo.svg" alt="PythonWoods" height="50" />
  </a>
  <p>
    <strong>Engineered with precision by PythonWoods in Italy 🇮🇹</strong><br/>
    <em>"Building the Standard for Technical Document Integrity."</em>
  </p>
  <p>
    <a href="https://zenzic.dev"><strong>Documentation</strong></a> &middot;
    <a href="https://github.com/PythonWoods"><strong>GitHub</strong></a> &middot;
    <a href="https://zenzic.dev/blog"><strong>Blog</strong></a>
  </p>
</div>

<!-- ─── Reference link definitions ──────────────────────────────────────────── -->

[mkdocs]:            https://www.mkdocs.org/
[zensical]:          https://zensical.org/
[uv]:                https://docs.astral.sh/uv/
[zenzic-action]:     https://github.com/PythonWoods/zenzic-action
[docs-home]:         https://zenzic.dev/
[docs-badges]:       https://zenzic.dev/how-to/add-badges/
[docs-cicd]:         https://zenzic.dev/how-to/configure-ci-cd/
[docs-arch]:         https://zenzic.dev/developers/how-to/implement-adapter
[docs-developers]:   https://zenzic.dev/developers/
[docs-eng-ledger]:   https://zenzic.dev/developers/explanation/adr-vault
[contributing]:      CONTRIBUTING.md
[license]:           LICENSE
[citation-cff]:      CITATION.cff
[coc]:               CODE_OF_CONDUCT.md
[security]:          SECURITY.md
[issues]:            https://github.com/PythonWoods/zenzic/issues
