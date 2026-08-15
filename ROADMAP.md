<!--
SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
SPDX-License-Identifier: Apache-2.0
-->

# Zenzic Roadmap

> **Governance Note (ADR-020):** This document is a root governance file. It is strictly **English-Only**. It must not be translated or mirrored in the `i18n/` directory.

This document describes the planned milestone trajectory for Zenzic, the **Deterministic Document Integrity Engine for Markdown/MDX graphs**.
Dates are targets, not commitments. All milestones are subject to revision.

For the current release history and completed milestones (up to `v0.29.x`), see [CHANGELOG.md](CHANGELOG.md).

---

## Immediate Infrastructural Priorities

Before advancing the core feature set, the following infrastructural and validation tasks are prioritized:

- **Empirical Benchmark Suite:** Audit large-scale open-source repositories (e.g., Kubernetes, Docusaurus) to empirically prove $O(N)$ complexity, sub-50ms latency, and static analysis capabilities against real-world documentation graphs.
- **OIDC/Entra ID CI/CD Integration:** Resolve VS Code Marketplace publishing technical debt by transitioning from legacy Personal Access Tokens (PAT) to Workload Identity Federation before the December 2026 deprecation deadline.

---

## Milestone Sequence

> For completed milestones (`v0.23` through `v0.29`), see [CHANGELOG.md](CHANGELOG.md).

### [v0.30] — Semantic Linting Supremacy

*Expanding AST-based semantic linting, structural accessibility, editorial style enforcement, and list heuristics.*

- `[x]` **Semantic Linting & Accessibility (`Z513`–`Z517`):** Native AST-based detection of duplicate headings, missing image alt text, bare URLs, multiple H1 headings, and heading punctuation.
- `[x]` **Editorial Style Enforcement (`Z518`, `Z519`, `Z617`–`Z619`):** Deterministic heuristics for passive voice, weasel words, forbidden/required content patterns, and document complexity.
- `[x]` **Semantic List Heuristics (`Z520`):** Automatic detection of malformed/fake lists formatted with semicolons/commas.

### [v0.31] — Docusaurus Bridge Architecture

*The first concrete implementation of the adapter ecosystem & automated remediation audit.*

- **`@zenzic/plugin-docusaurus`:** Validate the artifact-based Virtual Site Map (VSM) model outside the Python Core, allowing deterministic validation of Docusaurus routing without framework coupling.
- **Auto-Fix Audit for Non-Fixable Rules:** Perform a systematic AST audit across all `fixable=False` finding codes to identify viable candidates for atomic auto-remediation expansion in the Mutator engine.

### [v0.32] — Sphinx Adapter (GH #51)

*Extending open-source compatibility to the Python ecosystem.*

- **Native Sphinx Parsing:** Parse `conf.py` and `.rst` files natively without invoking the `sphinx-build` subprocess, translating Sphinx cross-references into the standard VSM.

### [v0.33] — Hugo Adapter (GH #50)

*Extending open-source compatibility to the Go ecosystem.*

- **Native Hugo Parsing:** Parse `hugo.toml` and frontmatter conventions to deterministically replicate Hugo's permalink generation rules within the Zenzic VSM.

### [v0.34] — Multi-Repository Documentation Graph & Connectivity (GH #7)

*Enterprise-scale topology validation & visual graph intelligence.*

- **Artifact Composition:** Allow Zenzic to aggregate multiple VSM artifacts to detect broken cross-repository references and routing inconsistencies across distributed documentation.
- **Smart Link Graph & Connectivity Analysis:** In-depth topological clustering and visual dead-end detection across interconnected documentation nodes.

### [v0.35] — Operational Excellence

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

Roadmap last updated: 2026-08-15.
