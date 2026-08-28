---
description: Why Zenzic focuses on structural integrity and security rather than prose style — and why that distinction defines a separate category of tool.
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Zenzic vs. Proofreader

Zenzic does not care about your writing style.

Whether you use hyphens or asterisks for lists, whether your lines are 80 or 120 characters
long, whether you prefer sentence case or title case in headings — none of these are Zenzic's
domain. These are matters of personal or team preference. They do not threaten your project's
stability, your users' safety, or your CI pipeline's reliability.

Excellent tools like `markdownlint`, `vale`, and `prettier` govern the **aesthetics of prose**.
Zenzic governs **Structural Integrity and Security**. These are not competing concerns —
they occupy orthogonal categories.

---

## The Integrity Filter {#integrity-filter}

Every rule that ships in the Zenzic Core must pass a three-dimensional admission test.
We call this **The Integrity Filter**: a rule enters Zenzic if and only if it defends
one of these three dimensions.

### Dimension 1 — Structural Integrity {#dimension-structural}

> *"Does this rule prevent a broken user experience?"*

A documentation project is a graph of interconnected resources. When a node in that graph
disappears — a file is renamed, a heading changes its anchor, a directory is restructured —
every reference pointing to that node becomes a ghost. The user follows the link and lands
on a 404. The CI pipeline succeeds. The damage is invisible at build time.

Structural Integrity rules catch these breaks **before the build runs**:

- **Orphan pages**: An orphan page is a Markdown file present on disk but absent from the site navigation declared in your build engine's configuration file. Because these pages are unreachable by users navigating the site structure, Zenzic reports them to keep you in control.
- **Comprehensive link checking**: Zenzic's link validation analyses all Markdown references, including text links, images, reference-style links, and same-page anchors.

| Finding Code | Name | What it catches |
| :--- | :--- | :--- |
| [`Z101`](../reference/finding-codes.md#z101) | `LINK_BROKEN` | Dead internal links — file not found |
| [`Z102`](../reference/finding-codes.md#z102) | `ANCHOR_MISSING` | Links to headings that no longer exist |
| [`Z106`](../reference/finding-codes.md#z106) | `CIRCULAR_LINK` | Circular link cycles — structural telemetry, not a defect (see [architectural rationale](../reference/finding-codes.md#z106)) |
| [`Z107`](../reference/finding-codes.md#z107) | `CIRCULAR_ANCHOR` | Self-referential anchor links |
| [`Z108`](../reference/finding-codes.md#z108) | `EMPTY_LINK_TEXT` | Empty or whitespace-only link labels |
| [`Z112`](../reference/finding-codes.md#z112) | `STALE_ALLOWLIST_ENTRY` | Unused entries in absolute path allowlist |
| [`Z401`](../reference/finding-codes.md#z401) | `MISSING_DIRECTORY_INDEX` | Directories without a reachable `index.md` |
| [`Z402`](../reference/finding-codes.md#z402) | `ORPHAN_PAGE` | Files unreachable from any navigation path |
| [`Z404`](../reference/finding-codes.md#z404) | `CONFIG_ASSET_MISSING` | Assets declared in config that do not exist on disk |

---

### Dimension 2 — Hardened Security {#dimension-security}

> *"Does this rule protect your infrastructure or secrets?"*

Documentation source is untrusted input. It is written by humans, accepted from external
contributors, and processed by build pipelines that may hold access to production credentials.
A single leaked API key in a Markdown file — committed in a rush, pushed to a public
repository — is a supply-chain incident, not an editorial oversight.

Security rules are **non-suppressible by design** — none of them can be silenced by
`zenzic:ignore`, and their exit codes bypass `--exit-zero` and `fail-on-error: false`
unconditionally. `Z202` is the one exception to the *exit code* pattern here: it stays a plain
exit 1 rather than escalating, but remains just as non-suppressible as the rest:

| Finding Code | Name | What it catches | Exit |
| :--- | :--- | :--- | :---: |
| [`Z201`](../reference/finding-codes.md#z201) | `CREDENTIAL_SECRET` | Credentials, API keys, tokens in any source line | 2 |
| [`Z202`](../reference/finding-codes.md#z202) | `PATH_TRAVERSAL` | Relative traversal patterns escaping the docs root | 1 |
| [`Z203`](../reference/finding-codes.md#z203) | `PATH_TRAVERSAL_FATAL` | Traversal targeting an OS system directory in a link or config value | 3 |

See [Exclusion Zone](./privacy-gate.md) and [The Zenzic Trinity](./the-zenzic-trinity.md)
for the complete exit code contract.

---

### Dimension 3 — Technical Accessibility {#dimension-accessibility}

> *"Does this rule ensure that third-party tools can consume your source?"*

Markdown is an input format: it is consumed by build engines, syntax highlighters, snippet
validators, and CI quality gates. Some structural properties that appear cosmetic at first
glance carry hard technical consequences for downstream tooling.

The canonical example is [`Z505: UNTAGGED_CODE_BLOCK`](../reference/finding-codes.md#z505):
a fenced code block with no language specifier renders as plain text in most engines. More
critically, it prevents snippet validation and breaks syntax highlighting coverage measurement.
The absence of a language tag is not a style preference — it is a missing machine-readable
contract between the author and every tool in the pipeline.

| Finding Code | Name | What it catches |
| :--- | :--- | :--- |
| [`Z505`](../reference/finding-codes.md#z505) | `UNTAGGED_CODE_BLOCK` | Fenced blocks with no language specifier |
| [`Z503`](../reference/finding-codes.md#z503) | `SNIPPET_ERROR` | Code snippets that fail to parse |
| [`Z106`](../reference/finding-codes.md#z106) | `CIRCULAR_LINK` | Link cycles — structural telemetry; documentation forms an interconnected Knowledge Graph where cycles are expected (see [architectural rationale](../reference/finding-codes.md#z106)) |
| [`Z108`](../reference/finding-codes.md#z108) | `EMPTY_LINK_TEXT` | Links whose label is empty or whitespace-only |

---

## The Node.js Tax and Architectural Independence {#the-nodejs-tax}

You might ask: why does Zenzic implement `Z505 (Untagged Code Blocks)` when static analysis tools
like `markdownlint` already detect this?

The answer is **[Pillar 2: Zero Subprocesses](../developers/explanation/governance/index.md#the-supreme-law-the-three-pillars)**.

Traditional Markdown tools require a full Node.js runtime and hundreds of megabytes of
`node_modules`. For a Python-based DevOps pipeline, a security-conscious enterprise, or any
team running CI in a minimal container, this dependency creates friction: additional toolchain
configuration, runtime version pinning, and transitive supply-chain exposure. We call this
the **Node.js Tax** — the hidden overhead of requiring a second runtime stack just to validate
documentation structure.

```text
Without Zenzic         With Zenzic
─────────────────────  ─────────────────────────
npm install            uvx zenzic check all
node_modules/ ~300 MB  (zero persistent install)
Node ≥ 18 required     Python 3.10+ required
npm audit surface      Zero transitive risk
```

By providing core structural checks in pure Python, Zenzic enables professional-grade
documentation quality **without leaving your primary technology stack**. Zenzic is not
designed to replace every quality check in your pipeline — but for structural integrity, security,
and technical accessibility in CI, it is the only one you **need**.

---

## What Zenzic Explicitly Does Not Do {#what-zenzic-does-not-do}

The boundary of what Zenzic rejects is as important as what it enforces. This table is
permanent. If a proposed rule does not pass The Integrity Filter, it does not ship.

| Category | Example | Position |
| :--- | :--- | :--- |
| Line length | Lines exceeding 80 or 120 characters | ✗ Not a structural concern |
| List marker style | `*` vs `-` vs `1.` | ✗ Aesthetic preference |
| Heading casing | Sentence case vs. Title Case | ✗ Editorial choice |
| Spell checking | Typos and grammar errors | ✗ Delegate to `vale` |
| Link text phrasing | "Click here" vs. descriptive anchor text | ✗ Guideline, not a gate |
| Trailing whitespace | Extra spaces at line endings | ✗ Auto-fixed by formatters |
| Prose consistency | Uniform use of terminology | ✗ Domain-specific — use `vale` |

These categories are not beneath Zenzic — they are **outside its mandate**. Zenzic
enforces the structure. Everything else is editorial sovereignty.

---

## The Recommended Layered Stack {#the-recommended-stack}

Zenzic works best as one layer in a quality stack, not as a replacement for the entire
tooling ecosystem:

| Layer | Tool | What it enforces |
| :--- | :--- | :--- |
| **Structural** | Zenzic | Broken links, orphans, secrets, path traversal |
| **Style** | `markdownlint` | List markers, heading levels, code fence format |
| **Prose** | `vale` | Grammar, terminology, style guides |
| **Format** | `prettier` | Consistent whitespace and indentation |

Configure each as an independent CI step. Zenzic's exit code contract is the
non-negotiable gate; the others can be advisories depending on your team's maturity model.

---

## Further Reading {#further-reading}

- [The Zenzic Trinity](./the-zenzic-trinity.md) — The three non-negotiable pillars: Zero Subprocesses, Pure Functions, Structural Analysis
- [Exclusion Zone](./privacy-gate.md) — The exit code contract and the inviolable security gate
- [Finding Codes Reference](../reference/finding-codes.md) — The complete Zxxx registry with remediation steps
- [Scoring System](./scoring-system.md) — How the Deterministic Quality Score is computed
