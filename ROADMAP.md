<!--
SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
SPDX-License-Identifier: Apache-2.0
-->

# Zenzic Roadmap

> **Governance Note (ADR-020):** This document is a root governance file. It is strictly **English-Only**. It must not be translated or mirrored in the `i18n/` directory.

This document describes the planned milestone trajectory for Zenzic, the **Deterministic Document Integrity Engine and SAST for Markdown/MDX graphs**.
Dates are targets, not commitments. All milestones are subject to revision.

For the current release history and completed milestones (up to `v0.23.x`), see [CHANGELOG.md](CHANGELOG.md).

---

## Immediate Infrastructural Priorities

Before advancing the core feature set, the following infrastructural and validation tasks are prioritized:

- **Empirical Benchmark Suite:** Audit large-scale open-source repositories (e.g., Kubernetes, Docusaurus) to empirically prove $O(N)$ complexity, sub-50ms latency, and SAST capabilities against real-world documentation graphs.
- **OIDC/Entra ID CI/CD Integration:** Resolve VS Code Marketplace publishing technical debt by transitioning from legacy Personal Access Tokens (PAT) to Workload Identity Federation before the December 2026 deprecation deadline.

---

## Milestone Sequence

### [v0.24] — Interactive Intelligence

*Completing the diagnostic-to-remediation loop within the IDE.*

- **VS Code Code Actions (Quick Fixes):** Implement `textDocument/codeAction` via LSP to allow users to instantly apply deterministic fixes (e.g., `Z121`, `Z603`) directly from the editor.
- **DQS Workspace UI:** Bring the Document Quality Score (DQS) into the authoring environment via a dedicated VS Code sidebar panel, providing global repository state without leaving the editor.

### [v0.25] — LSP Stabilization & Hot-Reloading

*Achieving 100% determinism between CLI and IDE via centralized governance, adapter-driven hot-reloading, and cross-platform URI parity.*

- **Centralized Governance Pipeline:** Eliminate CLI vs. LSP diagnostic drift by extracting `directory_policies` and `per_file_ignores` into core governance evaluation.
- **Adapter-Driven Config Hot-Reloading:** Enable real-time VSM topology rebuilds in VS Code when engine configuration files (e.g., `mkdocs.yml`, `zensical.toml`) change, without requiring an LSP server restart.
- **BaseAdapter Contract Hardening:** Expose `watched_config_files` on the `BaseAdapter` interface to preserve Adapter Neutrality across third-party engines.

### [v0.26] — Deterministic Quality Platform

*Evolving from a strict validator to a comprehensive quality governance engine.*

- **Smart Link Graph:** Transform the Virtual Site Map (VSM) into a full topological analysis engine capable of detecting documentation islands, circular navigation paths, and unreachable clusters.
- **Baseline & Regression Tracking:** Introduce evolutionary quality control. Essential for enterprise CI/CD to prevent DQS regressions over time.
- **Semantic Readability Metrics:** Extend Zenzic beyond structural validation into content quality (e.g., deterministic Flesch-Kincaid scoring) while maintaining the static analysis paradigm.
- **Configuration Validation Engine:** Reduce operational errors by establishing a single source of truth for configuration schemas across the CLI, VS Code, and documentation.

### [v0.27] — Governance & Extensibility

*Opening the engine to enterprise policies and custom integrations.*

- **Policy-as-Code Engine:** Formalize governance by transforming scattered configurations and ADRs into a verifiable, declarative model.
- **Custom Rule SDK v3:** Stabilize the analysis engine and sandbox to allow the community to build safe, deterministic custom rules.
- **SARIF Enterprise Integration:** Enhance security and compliance integrations for enterprise dashboards.
- **Zenzic Audit Mode:** High-value enterprise reporting mode requiring stable DQS, Policy Engine, and SARIF outputs.

### [v0.28] — Ecosystem Expansion

*Expanding the perimeter to external frameworks.*

- **Docusaurus Bridge Architecture:** The first concrete implementation of the adapter ecosystem, validating the artifact-based VSM model outside the Core.
- **Sphinx & Hugo Adapters:** Extend open-source compatibility following the stabilization of the `BaseAdapter` contract.
- **Multi-Repository Documentation Graph:** Advanced feature to analyze documentation spanning multiple repositories, requiring full maturity of the VSM and artifact composition.

### [v0.29] — Operational Excellence

*Advanced observability and developer experience.*

- **Performance Telemetry Engine:** Opt-in, deterministic metrics for operational governance and runtime optimization.
- **VS Code Configuration Autocomplete:** Inject JSON Schema validation into the IDE for `.zenzic.toml` files.

---

## Architectural Invariants (All Milestones)

These constraints apply across every future release. No feature may violate them.

| Invariant | Description |
|-----------|-------------|
| **Zero Subprocess** | `subprocess.Popen` and `os.system` permanently banned from `src/`. |
| **Pure Functions** | The analysis engine has zero global state. |
| **DFA Guarantee** | All regex matching backed by RE2. $O(N)$ complexity. |
| **Exit Code Contract** | Exit 2 = credential; Exit 3 = traversal. Never renumbered. |
| **No Inference** | Zero inference-engine (LLM/AI) runtime dependencies. |
| **Radical Unawareness** | The Core remains entirely unaware of external consumers (VS Code, GitHub Actions). |

---

Roadmap last updated: 2026-07-25.
