---
template: home.html
title: "Zenzic — Deterministic Document Integrity Engine"
hide:
  - navigation
  - toc
  - path
  - feedback
description: "Zenzic is a deterministic document integrity engine for Markdown/MDX graphs. Detect broken links, credential leaks, and topological defects before merge."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

## Core Capabilities

<div class="grid cards zz-features" markdown>

- :material-shield-lock-outline: &nbsp; **Security Enforcement**

    Detects hardcoded credentials (Z201), path traversal (Z202/Z203),
    and policy violations (Z610/Z611) before they reach production.
    Non-suppressible security findings exit 2 or 3 — never silenced.

    [:material-arrow-right: Security Reference](./reference/cli.md)

- :material-graph-outline: &nbsp; **Topological Graph Analysis**

    Virtual Site Map (VSM) builds an adjacency matrix over your document
    network — detecting orphaned pages, dead-end nodes, and broken
    cross-file links via Breadth-First Search.

    [:material-arrow-right: Graph Analysis](./reference/cli.md)

- :material-file-code-outline: &nbsp; **Policy-as-Code Engine**

    Declarative `[policies]` rules enforce governance constraints on
    frontmatter keys (Z610) and forbidden domain references (Z611)
    across every file in the workspace.

    [:material-arrow-right: Policy Configuration](./reference/configuration-reference.md)

</div>

---

## Why Zenzic?

Zenzic provides a deterministic quality architecture for your documentation suite,
with no probabilistic models or LLM dependencies.

<div class="zz-feature-row" markdown>

<div class="zz-feature-text" markdown>

### 100% Determinism and Baseline Tracking

Every Zenzic run is a pure function of its inputs. Given the same repository state and `.zenzic.toml`, the output — finding codes, severity levels, exit code, SARIF structure — is **bit-for-bit identical** across machines, platforms, and time.

With **Baseline and Regression Tracking**, existing technical debt can be recorded into a deterministic snapshot (`.zenzic-baseline.json`) via `--update-baseline`. Subsequent CI runs validate against `--baseline .zenzic-baseline.json` using line-shift invariant SHA-256 signatures, tagging baselined findings without dropping them (**Radical Unawareness**) and enforcing Document Quality Score (DQS) anti-regression rules.

</div>

<div class="zz-feature-visual">
<div class="zz-terminal" aria-label="Terminal: Baseline tracking commands" role="img">
  <div class="zz-terminal__bar">
    <span class="zz-terminal__dot zz-terminal__dot--red" aria-hidden="true"></span>
    <span class="zz-terminal__dot zz-terminal__dot--yellow" aria-hidden="true"></span>
    <span class="zz-terminal__dot zz-terminal__dot--green" aria-hidden="true"></span>
    <span class="zz-terminal__title">bash</span>
  </div>
  <div class="zz-terminal__body">
    <div class="zz-terminal__line"><span class="zz-terminal__meta"># Record existing technical debt into baseline snapshot</span></div>
    <div class="zz-terminal__line"><span class="zz-terminal__prompt">$</span><span class="zz-terminal__cmd">zenzic check all --update-baseline</span></div>
    <div class="zz-terminal__line" style="height: 0.5rem;"></div>
    <div class="zz-terminal__line"><span class="zz-terminal__meta"># Validate PR against baseline in CI/CD pipeline</span></div>
    <div class="zz-terminal__line"><span class="zz-terminal__prompt">$</span><span class="zz-terminal__cmd">zenzic check all --baseline .zenzic-baseline.json</span></div>
  </div>
</div>
</div>

</div>

<div class="zz-feature-row" markdown>

<div class="zz-feature-visual">
<div class="zz-terminal" aria-label="Terminal: Security finding" role="img">
  <div class="zz-terminal__bar">
    <span class="zz-terminal__dot zz-terminal__dot--red" aria-hidden="true"></span>
    <span class="zz-terminal__dot zz-terminal__dot--yellow" aria-hidden="true"></span>
    <span class="zz-terminal__dot zz-terminal__dot--green" aria-hidden="true"></span>
    <span class="zz-terminal__title">zsh — zenzic check all</span>
  </div>
  <div class="zz-terminal__body">
    <div class="zz-terminal__line zz-terminal__line--error"><span class="zz-terminal__code">[Z201]</span><span> Hardcoded AWS credential detected in docs/tutorial.md:42</span></div>
    <div class="zz-terminal__line zz-terminal__line--fatal">FAILED: Security boundary violated. Exit code 2.</div>
  </div>
</div>
</div>

<div class="zz-feature-text" markdown>

### Documentation as a Security Surface

Zenzic treats documentation as a **security surface**. The tiered code model enforces a hard boundary between quality findings (suppressible, exit 1) and security findings (non-suppressible, exit 2/3):

- **Z201 — Credential Scanner:** Hardcoded tokens, API keys, and secret patterns detected before reaching PRs.
- **Z202 / Z203 — Path Traversal Guard:** Filesystem boundary security violations caught at scan boundaries.
- **Suppression CAP:** Configurable ceiling on total active `zenzic:ignore` suppressions.

</div>

</div>

<div class="zz-feature-row" markdown>

<div class="zz-feature-text" markdown>

### Semantic Linting and Readability Metrics

Evaluate content quality without relying on probabilistic models or LLMs:

- **Z510 — Heading Hierarchy:** Detects skipped heading levels (e.g. H3 directly following H1).
- **Z511 — Excessive Sentence Length:** Enforces maximum sentence word count (`max_sentence_length = 40`).
- **Z512 — Empty Section:** Identifies heading sections containing no prose content before the next heading or EOF.

</div>

<div class="zz-feature-visual">
<div class="zz-terminal" aria-label="Terminal: Quality findings" role="img">
  <div class="zz-terminal__bar">
    <span class="zz-terminal__dot zz-terminal__dot--red" aria-hidden="true"></span>
    <span class="zz-terminal__dot zz-terminal__dot--yellow" aria-hidden="true"></span>
    <span class="zz-terminal__dot zz-terminal__dot--green" aria-hidden="true"></span>
    <span class="zz-terminal__title">zsh — zenzic check all</span>
  </div>
  <div class="zz-terminal__body">
    <div class="zz-terminal__line"><span class="zz-terminal__meta">docs/architecture.md:14</span></div>
    <div class="zz-terminal__line zz-terminal__line--error"><span class="zz-terminal__code">[Z511]</span><span> Sentence of 45 words exceeds limit of 40 words.</span></div>
    <div class="zz-terminal__line" style="height: 0.5rem;"></div>
    <div class="zz-terminal__line"><span class="zz-terminal__meta">docs/intro.md:8</span></div>
    <div class="zz-terminal__line zz-terminal__line--error"><span class="zz-terminal__code">[Z510]</span><span> Heading level skipped: H3 follows H1.</span></div>
  </div>
</div>
</div>

</div>

<div class="zz-feature-row" markdown>

<div class="zz-feature-visual">
<div class="zz-terminal" aria-label="Terminal: Topological Graph finding" role="img">
  <div class="zz-terminal__bar">
    <span class="zz-terminal__dot zz-terminal__dot--red" aria-hidden="true"></span>
    <span class="zz-terminal__dot zz-terminal__dot--yellow" aria-hidden="true"></span>
    <span class="zz-terminal__dot zz-terminal__dot--green" aria-hidden="true"></span>
    <span class="zz-terminal__title">zsh — zenzic check all</span>
  </div>
  <div class="zz-terminal__body">
    <div class="zz-terminal__line"><span class="zz-terminal__meta">docs/guide.md:16</span></div>
    <div class="zz-terminal__line zz-terminal__line--error"><span class="zz-terminal__code">[Z410]</span><span> 'intro.md' not reachable from nav or any document link.</span></div>
  </div>
</div>
</div>

<div class="zz-feature-text" markdown>

### Topological Graph Analysis (Smart Link Graph)

Beyond static link checks, Zenzic's Smart Link Graph constructs an adjacency matrix over your document network to perform Breadth-First Search (BFS):

- **Z410 — Unreachable Graph Node:** Documents completely isolated or unreachable from navigation entry points.
- **Z411 — Dead-End Node:** Documentation pages containing no outgoing links.

</div>

</div>

<div class="zz-feature-row" markdown>

<div class="zz-feature-text" markdown>

### Configuration Validation Engine

Formal schema validation for `.zenzic.toml` (`Z110` TOML syntax errors, `Z111` schema type mismatches) with exact line-number extraction. Fatal config errors halt document graph scanning to prevent false-positive cascades and protect LSP stability.

</div>

<div class="zz-feature-visual">
<div class="zz-showcase-card">
  <h4 style="margin-top: 0; margin-bottom: 0.5rem; color: var(--zz-ink-400); font-size: 0.75rem; font-family: 'JetBrains Mono', monospace; text-transform: uppercase; letter-spacing: 0.05em;">.zenzic.toml</h4>
  <pre style="color: var(--zz-ink-200); font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; line-height: 1.5;"><code><span style="color: var(--zz-brand-light);">[engine]</span>
<span style="color: var(--zz-terminal-meta);"># Validation prevents bad config execution</span>
max_sentence_length = <span style="color: var(--zz-success);">"40"</span> <span style="color: var(--zz-error);"># Z111: Expected int, got str</span>

<span style="color: var(--zz-brand-light);">[policies]</span>
disallowed_domains = [<span style="color: var(--zz-success);">"example.com"</span>]</code></pre>
</div>
</div>

</div>

---

## Quickstart

<div class="zz-terminal" aria-label="Terminal: zenzic check all output" role="img">
  <div class="zz-terminal__bar">
    <span class="zz-terminal__dot zz-terminal__dot--red" aria-hidden="true"></span>
    <span class="zz-terminal__dot zz-terminal__dot--yellow" aria-hidden="true"></span>
    <span class="zz-terminal__dot zz-terminal__dot--green" aria-hidden="true"></span>
    <span class="zz-terminal__title">zsh — zenzic check all</span>
  </div>
  <div class="zz-terminal__body">
    <div class="zz-terminal__line">
      <span class="zz-terminal__prompt">$</span>
      <span class="zz-terminal__cmd">uv tool install zenzic</span>
    </div>
    <div class="zz-terminal__line">
      <span class="zz-terminal__prompt">$</span>
      <span class="zz-terminal__cmd">zenzic init &amp;&amp; zenzic check all</span>
    </div>
    <div class="zz-terminal__line zz-terminal__line--error">
      <span class="zz-terminal__code">[Z104]</span>
      <span>'missing.md' resolves to nowhere — the target file does not exist.</span>
    </div>
    <div class="zz-terminal__line zz-terminal__line--fatal">FAILED: Hard errors detected. Exit code 1.</div>
  </div>
</div>

Or run directly with no installation:

```bash
uvx zenzic check all
```

---

## Ecosystem Delivery

Zenzic is structured into three dedicated delivery mechanisms to support your entire development workflow:

<div class="grid cards" markdown>

- :material-console-line: &nbsp; **Core Engine (CLI)**

    Python CLI with AST rule engine, Virtual Site Map topology analyzer,
    Policy-as-Code Engine, Custom Rule SDK v3, and Audit Mode.

    [:material-arrow-right: CLI Reference](./reference/cli.md)

- :material-github: &nbsp; **GitHub Action**

    Zero-setup CI/CD quality gate with SARIF upload, PR annotations,
    and Sovereign Audit mode. Pin the Core version for reproducible gates.

    [:material-arrow-right: GitHub Action Reference](./reference/zenzic-action.md)

- :material-microsoft-visual-studio-code: &nbsp; **VS Code Extension**

    Real-time LSP client delivering sub-50ms inline diagnostics,
    Policy-as-Code findings (Z610/Z611), Quick Fixes, and DQS scoring.

    [:material-arrow-right: Extension Guide](https://github.com/PythonWoods/zenzic-vscode)

</div>
