<!--
SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
SPDX-License-Identifier: Apache-2.0
-->

<p align="center">
  <a href="https://github.com/PythonWoods/zenzic">
    <img src="https://raw.githubusercontent.com/PythonWoods/zenzic/main/docs/assets/brand/svg/zenzic-logo.svg" alt="Zenzic Document Integrity Engine" width="480">
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

**Treat your Markdown documentation like production code.**

Zenzic detects broken links, orphaned pages, credential leaks, and structural integrity issues before they reach production.

---

## ⚡ Unified Ecosystem Platform

Zenzic is a unified, deterministic platform structured into three primary delivery mechanisms:

- **[Core Engine (CLI)](#-installation)**: Python CLI, AST rule engine, Virtual Site Map (VSM) topology analyzer, and **Baseline & Regression Tracking** (`.zenzic-baseline.json`).
- **[VS Code Extension][zenzic-vscode]**: Real-time LSP client offering sub-50ms inline diagnostics, Quick Fixes, and DQS scoring.
- **[GitHub Action][zenzic-action]**: Zero-config CI/CD quality gate with SARIF upload and PR annotations.

---

## 🚀 Deterministic 3-Step Quickstart (< 60 Seconds)

Experience zero-config topological failure detection in under 60 seconds:

```bash
# Step 1: Install Zenzic CLI
uv tool install zenzic

# Step 2: Initialize workspace and create a broken link
zenzic init
mkdir -p docs
echo "[broken](missing.md)" > docs/index.md

# Step 3: Run full documentation graph analysis
zenzic check all
```

**Expected Output:**

```text
docs/index.md:1  [Z104]  'missing.md' resolves to nowhere — the target file does not exist.

FAILED: Hard errors detected. Exit code 1 is mandatory.
```

### Next Steps: Real-Time Feedback

To eliminate the latency between authoring a defect and discovering it, install the [Zenzic VS Code Extension][zenzic-vscode] for real-time inline diagnostics and automated Quick Fixes.

---

## 🛡️ Why Zenzic?

### Determinism

Every Zenzic run is a pure function of its inputs. Given the same repository state and `.zenzic.toml`, the output — finding codes, severity levels, exit code, SARIF structure — is **bit-for-bit identical** across machines, platforms, and time. There are no probabilistic judgements, no LLM sampling, and no network-dependent results injected into the analysis path.

| Property | Guarantee |
| :--- | :--- |
| Same inputs → same output | ✅ Always |
| RE2-backed regex engine | ✅ No backtracking, no catastrophic matching |
| Frozen finding codes | ✅ `FROZEN_CODES` set; never renamed or silently retired |
| Reproducible CI artefacts | ✅ Identical SARIF across runner OS and time |

### Documentation Security (SAST)

Zenzic treats documentation as a **security surface**. The tiered code model enforces a hard boundary between quality findings (suppressible, exit 1) and security findings (non-suppressible, exit 2 / 3):

- **Z201 — Credential Scanner:** Hardcoded tokens, API keys, and secret patterns detected before they reach a PR.
- **Z202 / Z203 — Path Traversal Guard:** Filesystem boundary violations caught at the scan boundary.
- **Suppression CAP:** A configurable ceiling on the total number of active `zenzic:ignore` suppressions. Exceeding it blocks the build.

### Zero Hallucinations

Zenzic reports only what is **statically verifiable** in the repository at scan time. It never infers intent or approximates link validity. Every finding is a falsifiable, reproducible fact.

### Topological Graph Analysis (Orphans & Dead Ends)

Beyond static file checks, Zenzic's Smart Link Graph builds an adjacency list to perform Breadth-First Search (BFS) over your document network. It identifies **Topological Orphans** (`Z410`, documents unreachable from navigation entry points) and **Dead Ends** (`Z411`, pages with no outgoing links), helping maintain structural navigation integrity.

---

## 🧠 Key Capabilities & Commands

| Command | Purpose |
| :--- | :--- |
| `zenzic init` | Scaffold workspace configuration (`.zenzic.toml`) |
| `zenzic check all [PATH]` | Full documentation audit — links, credentials, orphans |
| `zenzic score [--stamp]` | Compute the Documentation Quality Score (0–100) |
| `zenzic diff [--base PATH]` | Detect debt regression against a saved baseline |
| `zenzic guard scan [PATH]` | Defense-in-Depth credential pre-gate (fatal on security findings) |
| `zenzic inspect codes` | Query live error-code semantics and suppressibility |

### Headless Data Pipeline (SARIF Output)

Zenzic Core is headless and emits standardized **SARIF** JSON, ensuring seamless integration with modern CI dashboards:

```json
{
  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "zenzic",
          "version": "0.26.5",
          "rules": [
            {
              "id": "Z101",
              "name": "BrokenLink"
            }
          ]
        }
      }
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

## 🔄 CI/CD & Responsibility Matrix (ADR-075)

Zenzic Core is **radically unaware** of any CI platform. Platform-specific behaviour — GitHub Annotations, Code Scanning upload, PR decoration — is the sole responsibility of the [Zenzic Action][zenzic-action].

```yaml
- uses: PythonWoods/zenzic-action@v2
  with:
    format: sarif
    upload-sarif: "true"
```

| Concern | Zenzic Core | [Zenzic Action][zenzic-action] |
| :--- | :---: | :---: |
| Link & Topology validation | ✅ | Executes Core |
| Credential scanner (Z2xx) | ✅ | Executes Core |
| Exit-code contract (0/1/2/3) | ✅ | Enforced |
| GitHub Annotations (`::error::`) | — | ✅ |
| Code Scanning SARIF upload | — | ✅ |
| PR inline diff annotations | — | ✅ |

---

## 📦 Installation & Upgrading

```bash
# Global CLI tool (Recommended)
uv tool install zenzic

# Pinned dev dependency
uv add --dev zenzic

# pip
pip install zenzic
```

If you installed Zenzic globally via `uv`, you must explicitly request an upgrade to fetch the latest deterministic engine:

```bash
uv tool upgrade zenzic
```

To run a specific version ephemerally without altering your global environment:

```bash
uvx zenzic@0.26.5 check all
```

---

## 📖 Documentation & Support

| Area | URL | Audience |
| :--- | :--- | :--- |
| 👤 User Guide | [zenzic.dev][docs-home] | Install, configure, CI/CD, finding codes |
| 🔧 Developer Portal | [zenzic.dev/developers][docs-developers] | Adapters, ADRs, CLI architecture |
| 🛡️ Security | [SECURITY.md][security] | Security reviewer |

---

## 🤝 Contributing

1. Open an [issue][issues] to discuss the change.
2. Read the [Contributing Guide][contributing].
3. Every PR must pass `just verify` and include SPDX headers on new files.

See also: [Code of Conduct][coc] · [Security Policy][security]

## 📎 Citing

A [`CITATION.cff`][citation-cff] is present at the root. Click **"Cite this repository"** on GitHub for APA or BibTeX output.

## 📄 License

Apache-2.0 — see [LICENSE][license]. This project strictly adheres to Semantic Versioning.

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
[zenzic-vscode]:     https://marketplace.visualstudio.com/items?itemName=pythonwoods.zenzic-vscode
[zenzic-action]:     https://github.com/PythonWoods/zenzic-action
[docs-home]:         https://zenzic.dev/
[docs-arch]:         https://zenzic.dev/developers/how-to/implement-adapter
[docs-developers]:   https://zenzic.dev/developers/
[contributing]:      CONTRIBUTING.md
[license]:           LICENSE
[citation-cff]:      CITATION.cff
[coc]:               CODE_OF_CONDUCT.md
[security]:          SECURITY.md
[issues]:            https://github.com/PythonWoods/zenzic/issues
