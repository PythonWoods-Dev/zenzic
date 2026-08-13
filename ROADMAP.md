<!--
SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
SPDX-License-Identifier: Apache-2.0
-->

# Zenzic Roadmap

> **Governance Note (ADR-020):** This document is a root governance file. It is strictly **English-Only**. It must not be translated or mirrored in the `i18n/` directory.

This document describes the planned milestone trajectory for Zenzic, the **Deterministic Document Integrity Engine for Markdown/MDX graphs**.
Dates are targets, not commitments. All milestones are subject to revision.

For the current release history and completed milestones (up to `v0.26.x`), see [CHANGELOG.md](CHANGELOG.md).

---

## Immediate Infrastructural Priorities

Before advancing the core feature set, the following infrastructural and validation tasks are prioritized:

- **Empirical Benchmark Suite:** Audit large-scale open-source repositories (e.g., Kubernetes, Docusaurus) to empirically prove $O(N)$ complexity, sub-50ms latency, and static analysis capabilities against real-world documentation graphs.
- **OIDC/Entra ID CI/CD Integration:** Resolve VS Code Marketplace publishing technical debt by transitioning from legacy Personal Access Tokens (PAT) to Workload Identity Federation before the December 2026 deprecation deadline.

---

## Milestone Sequence

> For completed milestones (`v0.23` through `v0.27`), see [CHANGELOG.md](CHANGELOG.md).

### [v0.28] — Governance & Extensibility

*Opening the engine to enterprise policies and custom integrations.*

- [x] **Policy-as-Code Engine:** Formalize governance by transforming scattered configurations and ADRs into a verifiable, declarative model. (Foundation released in v0.28.x)
- [x] **Custom Rule SDK v3:** Stabilize the analysis engine and sandbox to allow the community to build safe, deterministic custom rules. (Released in v0.28.x)
- [x] **SARIF Enterprise Integration:** Enhance security and compliance integrations for GitHub Code Scanning and enterprise dashboards. (Released in v0.28.x)
- [x] **Zenzic Audit Mode:** High-value enterprise compliance reporting command (`zenzic audit`) detailing active policies, DQS score, technical debt, and architectural state. (Released in v0.28.x)

### [v0.29] — Policy-as-Code Expansion

*Expanding governance policy evaluation, metadata validation, and link topology boundaries.*

- [x] **Taxonomic Refactoring:** Renamed finding code `Z118` to `Z620` (`STALE_GLOBAL_SUPPRESSION`) to align its identifier with the DQS Governance & Brand category and escalation amplifier.
- [x] **Metadata Governance Policies (`Z612`, `Z613`):** Declarative validation of required/forbidden frontmatter keys and schema matching.
- [x] **Link & Topology Governance (`Z614`–`Z616`):** Virtual Site Map (VSM) zero-trust link evaluation, forbidden URL schemes, and cross-namespace link boundaries.

### [v0.30] — Semantic Linting Supremacy

*Expanding AST-based semantic linting, structural accessibility, editorial style enforcement, and list heuristics.*

- **Semantic Linting & Accessibility (`Z513`–`Z517`):** Native AST-based detection of duplicate headings, missing image alt text, bare URLs, multiple H1 headings, and heading punctuation.
- **Editorial Style Enforcement (`Z518`, `Z519`, `Z617`–`Z619`):** Deterministic heuristics for passive voice, weasel words, forbidden/required content patterns, and document complexity.
- **Semantic List Heuristics (`Z520`):** Automatic detection of malformed/fake lists formatted with semicolons/commas.

### [v0.31] — Adapters & Ecosystem Expansion

*Expanding the perimeter to external frameworks and multi-repository graphs.*

- **Docusaurus Bridge Architecture:** The first concrete implementation of the adapter ecosystem, validating the artifact-based VSM model outside the Core.
- **Sphinx & Hugo Adapters:** Extend open-source compatibility following the stabilization of the `BaseAdapter` contract.
- **Multi-Repository Documentation Graph:** Advanced feature to analyze documentation spanning multiple repositories, requiring full maturity of the VSM and artifact composition.

### [v0.32] — Operational Excellence

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

Roadmap last updated: 2026-08-13.
