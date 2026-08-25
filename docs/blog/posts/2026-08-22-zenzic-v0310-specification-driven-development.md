---
title: "Zenzic v0.31.0: Specification-Driven Development & AI Knowledge Graph Integrity"
slug: zenzic-v0310-specification-driven-development
date: 2026-08-22
authors:
  - pythonwoods
description: >
  Zenzic v0.31.0 introduces Specification-Driven Development (SDD): native Table AST parsing,
  declarative table column enforcement (Z521), cell value enums (Z522), heading sequence validation (Z523),
  and multi-namespace graph traceability (Z412) to protect knowledge graphs from AI hallucinations.
categories:
  - Releases
  - Engineering
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

![Zenzic v0.31.0: Specification-Driven Development & AI Knowledge Graph Integrity](../../assets/images/blog/launch_v0310.webp)

> **Formatters handle syntax. Prose linters handle grammar. Zenzic protects the graph—and optionally enforces lightweight editorial policy without a separate tool.**

Technical documentation has traditionally been treated as a publishing problem.

We write Markdown, build a static site, check links, fix spelling mistakes, and review the result before publication. The tools involved are consequently familiar: formatters, prose linters, spell checkers, link checkers, and static-site build systems.

That model works well when documentation is primarily intended for human reading.

It becomes incomplete when documentation starts carrying engineering contracts.

Requirements live in Markdown. Architecture decisions live in Markdown. Design specifications, operational procedures, acceptance criteria, and implementation constraints live in Markdown. Increasingly, those documents are also consumed by automation and AI-assisted development tools — the kind that are remarkably good at writing Markdown that *looks* correct, without any way of knowing which parts of that Markdown are load-bearing.

Here's a real shape of the problem: an agent is asked to add a new endpoint to an API reference table. It does. But the table it regenerates looks like this:

```markdown
| Endpoint | Method |
| :--- | :--- |
| /v1/users | GET |
| /v1/sessions | POST |
```

Looks fine, right? Except the original contract for that table required an `Auth` column — every endpoint needs to document whether it's public, requires a bearer token, or needs an admin scope. The agent generated a plausible, well-formatted table. It just didn't know, and had no way of enforcing, that `Auth` was a mandatory field in *this specific table*, in *this specific document*. Nothing in Markdown syntax says a table must have a given column. Nothing in prose grammar catches it either.

At that point, the important question is no longer only whether a document is readable.

It is whether the document still satisfies the rules that give it meaning.

A requirements table can be valid Markdown and still be incomplete. A status field can contain a plausible value and still violate the project's vocabulary. A document can contain all the right information and still put its sections in an order that breaks the expected specification template. A specification can exist and still be disconnected from the documents that are supposed to provide traceability to it.

These are not formatting errors.

They are failures of documentation governance — a slow, silent erosion of a knowledge graph's integrity, one plausible-looking PR at a time.

Zenzic v0.31.0 introduces a Specification-Driven Development (SDD) rule suite aimed at this layer of the problem: native Table AST parsing, declarative table column enforcement, cell value enums, heading sequence validation, and multi-namespace graph traceability.

The significance is not simply that four more rules exist.

It is that documentation analysis can now express part of the contract that a project places around its specifications.

<!-- more -->

---

## Why Deterministic Static Analysis, Not LLMs

A common modern instinct is to prompt an LLM to "review documentation quality" on every pull request. In production engineering, this approach fails on three fundamental axes:

1. **Latency & Execution Speed**: Zenzic compiles and validates hundreds of Markdown files in under 15 milliseconds via a single-pass $O(N)$ AST and Virtual Site Map (VSM) topology. An LLM review takes 5 to 15 seconds per file, creating unacceptable CI pipeline bottlenecks.
2. **Zero Inference Cost**: Zenzic runs locally, in pre-commit hooks, and in CI/CD with zero API keys, zero token fees, and zero external network calls.
3. **Deterministic CI Contracts**: Static analysis produces reproducible, bit-exact exit codes (`0` for clean, `1` for quality, `2` for security leaks, `3` for traversal incidents) and a mathematically verified Document Quality Score (DQS). LLM evaluations are stochastic, non-reproducible, and prone to the very hallucinations they are tasked to detect.

An AI system consuming a repository does not automatically know which parts of the documentation are authoritative, which values are permitted, which sections are mandatory, or which relationships are required by the development process. If those constraints exist only as conventions in people's heads, they are difficult to enforce consistently. If they are encoded as Policy-as-Code, they become part of the repository's executable contract — and the purpose is not to ask an AI model to determine whether a document "looks consistent." It is to make objective properties deterministic.

---

## The Modern Documentation Stack

Zenzic fits alongside your existing formatting and prose tooling without overlap:

| Capability / Layer | Syntax Formatters | Prose Linters | Zenzic (DQP / SDD Engine) |
| :--- | :---: | :---: | :---: |
| **Markdown Syntax & Whitespace** | :material-check-circle:{ .zenzic-score-100 } Native | :material-minus-circle-outline: Out of Scope | :material-minus-circle-outline: Delegated to Formatters |
| **Spelling & Natural Language Grammar** | :material-minus-circle-outline: Out of Scope | :material-check-circle:{ .zenzic-score-100 } Native | :material-minus-circle-outline: Complementary / Compatible |
| **Lightweight Editorial Policy**¹ | :material-minus-circle-outline: Out of Scope | :material-alert-circle-outline: Requires External Rules | :material-check-circle:{ .zenzic-score-100 } Built-in Opt-In (`[policies]`) |
| **AST Table Contract Enforcement (Columns/Enums)** | :material-minus-circle-outline: Out of Scope | :material-minus-circle-outline: Out of Scope | :material-check-circle:{ .zenzic-score-100 } Native SDD Engine (`Z521`, `Z522`) |
| **Heading Structure & Sequential Templates** | :material-minus-circle-outline: Out of Scope | :material-minus-circle-outline: Out of Scope | :material-check-circle:{ .zenzic-score-100 } Native SDD Engine (`Z523`) |
| **Multi-Namespace Graph Traceability** | :material-minus-circle-outline: Out of Scope | :material-minus-circle-outline: Out of Scope | :material-check-circle:{ .zenzic-score-100 } Native VSM Topology (`Z412`) |
| **Zero-Leak Secret & Privacy Gate (Non-Suppressible)** | :material-minus-circle-outline: Out of Scope | :material-minus-circle-outline: Out of Scope | :material-check-circle:{ .zenzic-score-100 } Native Security Engine (`Z201`–`Z205`) |
| **Deterministic DQS Mathematical Score (0–100)** | :material-minus-circle-outline: Out of Scope | :material-minus-circle-outline: Out of Scope | :material-check-circle:{ .zenzic-score-100 } Native Algorithmic Ledger |

¹ *Note: Zenzic's editorial policy checks (such as passive voice `Z518` and weasel words `Z519`) are lightweight RE2-based regex heuristics designed for fast CI guardrails, not full natural language grammar parsing.*

---

## From document quality to specification integrity

There is an important distinction between a document being well formed and a document being correct for its role.

Consider a simple requirements table:

| ID      | Requirement              | Status |
| ------- | ------------------------ | ------ |
| REQ-001 | Users can export reports | stable |

From a Markdown parser's perspective, this is an ordinary table.

From an engineering team's perspective, however, the table may have a schema. Perhaps every requirement must also specify an owner:

| ID      | Requirement              | Status | Owner     |
| ------- | ------------------------ | ------ | --------- |
| REQ-001 | Users can export reports | stable | reporting |

Markdown does not know that the `Owner` column is mandatory. That requirement exists outside the syntax of the document.

The same is true for allowed values. If `Status` is defined as `draft`, `review`, or `stable`, then `approved`, `complete`, or `final` may be meaningful words but still be invalid states for this particular specification. Again, the Markdown is syntactically valid. The specification is not.

This distinction is the foundation of the new SDD rule suite.

---

## Four failure modes, four rules

Each new rule targets a distinct, previously unenforceable way a specification can drift from its own contract:

| Failure Mode | Rule | What Breaks |
| :--- | :--- | :--- |
| Missing schema | [`Z521`](../../rules/Z521.md) | A required table column silently disappears |
| Invalid state | [`Z522`](../../rules/Z522.md) | A cell contains a value outside the approved vocabulary |
| Structural drift | [`Z523`](../../rules/Z523.md) | Sections exist but no longer follow the required order |
| Broken traceability | [`Z412`](../../rules/Z412.md) | A specification exists but is disconnected from its source graph |

### Z521 — Required table columns

[`Z521`](../../rules/Z521.md) (`REQUIRED_TABLE_COLUMN`) enforces mandatory table headers declared through Policy-as-Code configuration. The policy can apply globally or to a specific section, depending on the configured scope.

```toml
[policies.required_table_columns]
"*" = ["Status", "Description"]
"^API Reference$" = ["Method", "Endpoint", "Auth"]
```

```markdown
<!-- Emits Z521: missing required 'Status' column -->
| Endpoint | Method |
| :--- | :--- |
| /v1/users | GET |
```

![Real `zenzic check all --only Z521` output showing two Z521 findings for missing required table columns](../../assets/images/terminal/z521-finding.webp)

Conceptually, the rule allows a project to say: *every table of this kind must expose these fields.* That turns an implicit template convention into an executable constraint. Without such a rule, the organization has to rely on documentation templates, reviewer memory, manual inspection, or an external process that notices missing fields after the fact. With the rule, the table structure becomes machine-checkable — particularly useful for requirement matrices, decision records, inventories, and status tables, where the columns themselves carry semantic meaning.

### Z522 — Table cell enumerations

A table can have the correct columns and still contain invalid data. [`Z522`](../../rules/Z522.md) (`TABLE_CELL_ENUM`) addresses this case. Projects can declare predefined sets of permitted values for table cells; matching is case-insensitive, and findings identify the relevant data row precisely.

```toml
[policies.table_cell_enums]
"Status" = ["draft", "review", "stable", "deprecated"]
```

```markdown
<!-- Emits Z522: 'unknown_status' is not in ['draft', 'review', 'stable', 'deprecated'] -->
| Feature | Status |
| :--- | :--- |
| AST Engine | unknown_status |
```

![Real `zenzic check all --only Z522` output showing a Z522 finding for an out-of-vocabulary cell value](../../assets/images/terminal/z522-finding.webp)

This is a small mechanism with an important consequence: it allows teams to move from "please use one of these values" to "these are the values the specification permits." That difference matters whenever tables become inputs to automation — a controlled vocabulary is only controlled if deviations can be detected.

### Z523 — Heading order

Specifications frequently have an expected structure. For example, an organization may require documents to progress through Context, Requirements, Constraints, Decision, and Consequences. The precise template is project-specific — what matters is that the order itself may carry meaning.

[`Z523`](../../rules/Z523.md) (`HEADING_ORDER_VIOLATION`) allows an ordered document-section template to be declared through policy:

```toml
[policies]
required_heading_order = [
    "^Overview$",
    "^Prerequisites$",
    "^Installation$",
    "^Usage$",
    "^API Reference$"
]
```

This addresses a form of drift that is otherwise surprisingly difficult to detect: a document may contain every required heading and therefore appear complete when inspected casually, yet the sections may be reordered, or a new document may evolve a slightly different structure from the rest of the specification set. The resulting problem is not necessarily that humans can no longer read the document — it is that the corpus no longer has a stable structural contract. A predictable structure makes documents easier to review, compare, transform, and consume programmatically.

### Z412 — Broken traceability

The fourth addition is different because it operates at the graph level. [`Z412`](../../rules/Z412.md) (`TRACEABILITY_BROKEN`) enforces inbound graph-link coverage from designated source namespaces to target specification documents declared through `traceability_targets`.

```toml
[policies.traceability_targets]
"specs/**" = ["architecture/**", "epics/**"]
"adrs/**" = ["rfcs/**"]
```

If a document matching `docs/specs/auth-sdd.md` lacks inbound links from `docs/architecture/**` or `docs/epics/**`, Zenzic emits `Z412 TRACEABILITY_BROKEN`.

This addresses a common weakness in documentation systems: a specification can exist as a perfectly valid file while remaining disconnected from the rest of the knowledge base. Suppose a project organizes its documentation into `requirements/`, `specifications/`, `design/`, and `decisions/`. A requirement may be expected to lead to a specification; a specification may then lead to a design document or architectural decision. Those relationships form a graph. A file-level linter can establish that the files exist. It cannot, by itself, establish that the required relationships exist. Traceability validation introduces that missing constraint — the question becomes not merely *does the specification exist?* but *is the specification connected to the source material that is required to justify or drive it?* That is a substantially different kind of analysis.

---

## The SDD Architecture: Beyond Syntax and Grammar

Traditional documentation linters operate on isolated source files, checking whitespace or dictionary spelling. Zenzic treats documentation as a compiled, interconnected graph.

```text
  AI Agents / Engineers ───> Markdown Specs ───> [ ZENZIC COMPILER ] ───> Verified Knowledge Graph
                                                   │
                                                   ├── O(N) AST Table & Semantic Validation
                                                   ├── Virtual Site Map (VSM) Topo-Routing
                                                   ├── Multi-Namespace Graph Traceability
                                                   └── Zero-Tolerance Security Gates (Exit 2/3)
```

With v0.31.0, the core parser expands with a first-class **Table Abstract Syntax Tree (AST)** — `TableNode`, `TableRow`, and `TableCell` — that represents GitHub Flavored Markdown (GFM) tables with zero subprocess overhead, byte-for-byte lossless round-tripping, and strict RE2 non-backtracking safety.

This implementation detail matters because table validation is only as reliable as the parser underneath it. A simplistic split-on-pipe implementation can misinterpret escaped pipes or pipes inside inline code spans. For a rule such as `Z522`, an incorrect parse can produce an incorrect finding. The objective of the new parser is therefore not merely convenience — it provides the structural representation required for deterministic table analysis without unnecessarily changing the source document.

---

## Why this matters for Specification-Driven Development

Specification-Driven Development depends on the assumption that specifications are reliable inputs to subsequent engineering work. That assumption becomes weaker as specifications drift.

Imagine a development workflow in which requirements are written first and implementation is derived from them. A missing table field may remove an important property. An invalid enum may introduce ambiguity about state. A reordered template may make automated extraction unreliable. A missing traceability link may disconnect an implementation constraint from the requirement that introduced it.

None of these failures necessarily produces invalid Markdown.

They produce invalid context.

---

## Policy-as-Code becomes more expressive

The new rules extend the policy model with four corresponding configuration concepts: `required_table_columns`, `table_cell_enums`, `required_heading_order`, and `traceability_targets`.

This is an important architectural boundary. The rules themselves are generic. The project decides what they mean. A documentation tool should not decide that every organization needs the same requirement schema, the same status vocabulary, or the same heading sequence. Instead, the engine provides enforcement primitives while the repository provides policy — a separation that allows the same analysis engine to operate across different documentation systems without turning project conventions into hard-coded assumptions.

---

## The rest of the release matters too

The SDD rule suite is the most obvious functional addition, but it is not the only architectural change in the release.

**Smart engine discovery.** The build-engine discovery logic was refined to identify Zensical projects configured through the appropriate configuration format without invoking a full YAML parser for that detection path. This is part of a broader design principle in Zenzic: static analysis should not require executing the documentation build system. Zenzic reads configuration as data rather than running the build engine or its plugins.

**DQS transparency.** The `zenzic score` command gains a `--breakdown` option. A single quality score can be useful for tracking, but a score without an explanation is difficult to act upon — the breakdown exposes the scoring ledger, including category deductions, the Gravity Cap calculation, and technical-debt mathematics. This follows the same principle as the rule system itself: a quality signal is more useful when its origin can be inspected.

![Real `zenzic score --breakdown` output showing the per-category scoring ledger](../../assets/images/terminal/score-breakdown.webp)

**LSP determinism for topological findings.** The release also formalizes how topological findings are handled by the Language Server Protocol integration. For findings that cannot meaningfully be suppressed with an inline comment, the LSP should not offer a misleading source edit — instead, it explains that suppression belongs in the appropriate configuration mechanisms. This is a small interaction detail, but it illustrates a broader principle: tooling should not offer an action that contradicts the semantics of the underlying rule.

---

## Ecosystem-Wide Parity & The 10-Target Mirror Law

Like all Zenzic capabilities, Specification-Driven Development is governed by the **Mirror Law (ADR-020)** — ensuring 100% synchronous parity across all 10 mandatory targets: Core codes, Scorer, Scoring documentation, Finding Codes catalog, Rule Specification Cards, MkDocs navigation, Lab scenarios, `zenzic init` templates, VS Code IntelliSense schemas, and Test suites.

The reason for such a protocol is straightforward. When the same contract is represented in several places, those representations can drift. A rule can exist in the engine but disappear from the documentation. A configuration option can exist in the parser but not in the generated template. A finding code can be emitted by the analyzer but be absent from the reference documentation. Parity checks make those inconsistencies visible.

Across the ecosystem, this parity is what makes the same contract usable in three places at once:

1. **Zenzic CLI**: Fast terminal execution (`zenzic check all`) with rich terminal diagnostics, SARIF v2.1.0 output, and DQS scoring.
2. **VS Code Extension (LSP)**: Instant real-time diagnostic squiggles inside VS Code as you edit Markdown tables or reorder headings, backed by the updated `zenzic.schema.json`.
3. **GitHub Actions (`zenzic-action`)**: Zero-config CI/CD quality gate (`v2`) stopping untraceable or malformed specifications on pull requests.

---

## Deterministic checks have a specific role

There will always be questions that cannot be reduced to static rules. A machine can verify that a heading exists. It cannot determine whether the decision described under that heading is the right decision for the business. A machine can verify that a requirement has an owner. It cannot determine whether that owner is the correct person. A machine can verify that a specification is linked to a requirement. It cannot determine whether the specification actually fulfills the requirement.

Those remain review questions.

The role of deterministic analysis is narrower and, precisely because of that, useful: it removes objective checks from the subjective review process. Reviewers should not have to spend their attention discovering that a mandatory column is missing or that a value falls outside an approved vocabulary. Those checks can be automated. Human attention can then be reserved for questions that actually require judgment.

---

## Adoption does not require rewriting the documentation system

An important property of this approach is that specification governance does not have to be introduced as a complete documentation transformation.

Zenzic can already run directly against Markdown repositories, including repositories without a framework-specific documentation engine. It can also operate through local development, pre-commit, CI, and one-off audits. The practical adoption path can therefore remain incremental:

1. Run the existing checks.
2. Establish a baseline.
3. Identify the documentation contracts that actually matter.
4. Encode those contracts as policies.
5. Introduce the corresponding rules gradually.
6. Move enforcement toward the development workflow.

This matters because governance that requires a documentation migration before it produces value is difficult to adopt. The useful constraint is the opposite: add enforcement around the documentation system that already exists.

---

## Try It in 30 Seconds

The fastest way to see this on your own repository is the pre-commit hook — no global install, no environment pollution, just an isolated, pinned check on your staged files:

<!-- Publication gate: do not publish before the v0.31.0 tag exists on GitHub. -->

```yaml title=".pre-commit-config.yaml"
repos:
  - repo: https://github.com/PythonWoods/zenzic
    rev: v0.30.0
    hooks:
      - id: zenzic-guard
```

(`rev:` should track the latest tagged release rather than being copy-pasted indefinitely — check the repository's release tags before pinning.)

If you just want to point Zenzic at a repository for a one-off local test without adding it to your workflow yet, you can run it ephemerally with `uvx`, pinned to a specific version:

```bash
# One-off local test only — not the recommended default workflow
uvx zenzic@0.30.0 check all
```

Add your project's SDD policies to `.zenzic.toml`:

```toml
[policies]
required_heading_order = ["^Overview$", "^API Reference$"]

[policies.required_table_columns]
"*" = ["Status", "Description"]

[policies.table_cell_enums]
"Status" = ["draft", "review", "stable"]

[policies.traceability_targets]
"specs/**" = ["architecture/**"]
```

Run `zenzic check all` to verify your documentation graph.

---

## What changes with v0.31.0

The most important change in v0.31.0 is therefore not the number of new finding codes.

It is the boundary of what documentation tooling is expected to understand.

A documentation integrity engine does not need to understand the business meaning of every sentence. It does need to understand when a project has declared an objective contract and whether the repository still satisfies that contract: required table columns, controlled values, heading order, traceability. These are simple enough to verify deterministically and important enough to justify verification. That combination makes them good candidates for Policy-as-Code.

Once documentation participates in requirements, architecture, implementation, and AI-assisted workflows, its quality cannot be defined only by appearance. The relevant question becomes whether the documentation still behaves according to the system that depends on it — which requires syntactic integrity, editorial integrity, reference integrity, topological integrity, and specification integrity. Zenzic v0.31.0 extends the last layer. It does not attempt to make human review unnecessary. It makes more of the mechanical part of that review explicit, reproducible, and enforceable.

That is the useful boundary for deterministic tooling:

> **Do not automate judgment. Automate the contracts that should never depend on judgment.**

**Specifications require deterministic enforcement.** See [Deterministic Tooling and the Distribution Boundary Problem](2026-08-23-deterministic-tooling-and-pre-commit.md) for how that enforcement reaches your team without introducing the very drift it's meant to prevent.
