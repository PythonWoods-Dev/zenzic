<!--
SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
SPDX-License-Identifier: Apache-2.0
-->

# Zenzic Roadmap

> **Governance Note (ADR-020):** This document is a root governance file. It is strictly **English-Only**. It must not be translated or mirrored in the `i18n/` directory.

This document describes the planned milestone trajectory for Zenzic, the **Deterministic Document Integrity Engine for Markdown/MDX graphs**.
Dates are targets, not commitments. All milestones are subject to revision — and a revision is recorded here with its reason, never applied silently: a withdrawn commitment is explained, not deleted.

For the current release history and completed milestones (up to `v0.30.x`), see [CHANGELOG.md](CHANGELOG.md).

---

## Immediate Infrastructural Priorities

Before advancing the core feature set, the following infrastructural and validation tasks are prioritized:

- **Empirical Benchmark Suite:** Audit large-scale open-source repositories (e.g., Kubernetes, Docusaurus) to empirically prove $O(N)$ complexity, sub-50ms latency, and static analysis capabilities against real-world documentation graphs.
- **OIDC/Entra ID CI/CD Integration:** Resolve VS Code Marketplace publishing technical debt by transitioning from legacy Personal Access Tokens (PAT) to Workload Identity Federation before the December 2026 deprecation deadline.

---

## Milestone Sequence

> For completed milestones (`v0.23` through `v0.30`), see [CHANGELOG.md](CHANGELOG.md).

### [v0.31] — Epic 3: Specification-Driven Development (SDD)

*Validating AI-generated technical documentation, structured table semantics, heading sequence, and graph traceability.*

- **AST Table Extraction (`TableNode`):** Native $O(N)$ table parsing in the core polyglot extractor without external parser dependencies.
- **Table Semantics (`Z521`, `Z522`):** Deterministic enforcement of required table columns (`Z521`) and allowed cell enumeration values (`Z522`).
- **Heading Order Enforcement (`Z523`):** Sequence validation for required heading patterns (e.g., "Overview" preceding "API").
- **Graph Traceability (`Z412`):** Cross-directory documentation link coverage verification evaluated natively via the Virtual Site Map (VSM).
- **Ecosystem Marketing & Positioning Overhaul:** Positioning Zenzic as the premier document integrity engine protecting documentation graphs against AI slop.

The release also carries two breaking changes to what the security tier reads and what an absolute link to a system directory means; both are stated under the upgrade notice in [CHANGELOG.md](CHANGELOG.md), and a corpus that passes today can fail after upgrading. Read that notice before rolling the version into a gate.

### [v0.31.x] — Patch releases after the tag

*Work whose cost is measured and small, held off the release only because it changes a parsing hot path or a published number while the release is being cut.*

- **One reference-definition rule:** four modules carry their own regular expression for a Markdown link reference definition, in four spellings, and only one of them excluded footnote labels until 2026-09-13. One function, five call sites, one stated rule.
- **Mutant triage with identities:** the mutation gate now records each mutant's fate beside the aggregate score, so the four mutants killed under Python 3.10 and surviving under 3.14 can be named rather than counted. The triage is a local session against the expanded module set.
- **Visual consistency pass:** the documentation palette is already variable-driven (rule-card icons and diagrams derive their colours from the theme, enforced by a gate); what remains is the site stylesheet's own literals and a decision on typography and spacing, then re-capturing the assets that carry the brand.

### [v0.32] — Auto-Fix Audit & CommonMark Conformance

*Widening what the engine repairs, and making what it reads conform to the specification rather than to one generator's habits.*

- **Auto-Fix Audit for Non-Fixable Rules:** Perform a systematic AST audit across all `fixable=False` finding codes to identify viable candidates for atomic auto-remediation expansion in the Mutator engine.
- **CommonMark Conformance:** the fenced-code-block state machine already follows CommonMark §4.5 and every consumer shares it. This milestone extends the same discipline to the constructs the engine still reads by habit — **HTML blocks (§4.6) as a first-class construct**, not an appendix: their seven start conditions, where they end, and what inside them is inert to every quality rule while remaining in scope for the security tier; indented code (§4.4); link reference definitions (§4.7) with one rule for all consumers. Conformance work takes the place of further adapters, and each construct ships with the specification's own examples as fixtures.
- **CLI/LSP Finding Parity — the part that remains:** the two analysis paths now build the same link graph (they differ by one edge in about 790, a `?q=` link, after the trailing-slash defect was fixed on the release branch), and the cycle pass runs on both. What still differs is deliberate and named: the editor surfaces no `info`-severity finding by design, and the CLI's nav-membership codes (`Z402`, `Z403`) and the VSM's reachability codes (`Z410`–`Z412`) answer two different questions. Unifying the second pair is an architectural decision this milestone will take or decline explicitly.

### [v0.33] — Multi-Repo Graph (GH #7)

*Distributed graph validation across polyrepo documentation architectures.*

- **Artifact Composition & Connectivity Analysis:** Aggregate multiple VSM artifacts to detect broken cross-repository references and routing inconsistencies across distributed documentation.
- **Anchors a Markdown extension mints:** `pymdownx.tabbed` with `combine_header_slug` produces anchors the engine's own slugifier cannot reproduce (0 of 3 on a measured foreign corpus; 464 tab titles in 39 files there, 29 in 6 here), and the Core must not import a generator's library (Radical Unawareness, ADR-075). Detection is already free — the setting is read from the engine configuration — so what this milestone needs is a declared, parameterised slug contract rather than a dependency.

### [v0.34] — Operational Excellence

*Advanced observability, developer experience, and incremental performance.*

- **Synthetic Benchmark Corpus & CLI Incremental Cache:** Large-scale benchmark generation (100–5,000 files) and `.zenzic_cache/vsm.db` disk caching for sub-100ms incremental local scans — and, from the same corpus, a measured answer to whether a compiled hot path is ever warranted, rather than an assumed one.
- **Performance Telemetry Engine:** Opt-in, deterministic metrics for operational governance and runtime optimization.
- **VS Code Configuration Autocomplete:** Inject JSON Schema validation into the IDE for `.zenzic.toml` files.

---

## Retired, With the Reason

Commitments this roadmap once made and has withdrawn. They stay here because a reader who saw the promise deserves to find the reason, not an absence.

- **Sphinx adapter (GH #51) — retired 2026-09-15, planned for v0.32 until then.** Three reasons, each measured rather than assumed: Sphinx caches parsed sources as doctree pickles under `.doctrees`, and a Python pickle cannot be read without risking code execution, which the Zero Subprocess and No Inference invariants forbid; reStructuredText is not Markdown, so an adapter would have to add a parser rather than map files to routes, which is not what an adapter is; and Sphinx ships `linkcheck`, which already answers the central question for that ecosystem. What would reopen it: a Sphinx that emits a machine-readable route manifest, which the `prebuilt` engine already consumes.
- **Docusaurus and Astro adapters — covered, not built.** Measured on a Docusaurus site at 8 findings down to 2 using the `prebuilt` engine with a route manifest, so the coverage is delivered without a dedicated adapter. A dedicated adapter would reopen only if the manifest route proves insufficient on a real corpus.
- **Hugo adapter — deferred to the community**, tracked in [GH #50](https://github.com/PythonWoods-Dev/zenzic/issues/50). Unchanged by the Sphinx decision.

## Considered, Not Scheduled

Capabilities judged legitimate but not committed. They carry no version deliberately: an
unassigned entry is more honest than a date nobody chose. Each records what would change the
assessment, so revisiting it is a decision rather than a rediscovery.

*Nothing is currently listed here.* The first entry — a user-declared list of link components —
was **implemented instead**, in `v0.31`, and by a different design: the engine recognises any
capitalised tag carrying `to`, `href` or `src`, which is the JSX convention rather than a
configurable list, so nothing has to be declared and a component nobody has invented is covered.
The entry lived here for less than a day, which is itself the argument for keeping this section
honest: a consideration that becomes work should leave, not linger as a plan nobody is following.

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

Roadmap last updated: 2026-09-17.
