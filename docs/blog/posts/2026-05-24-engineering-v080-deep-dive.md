---
title: "Engineering Deep Dive: v0.8.0 Architecture"
date: 2026-05-24
authors:
  - pythonwoods
description: "Engineering Deep Dive: v0.8.0 Architecture"
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

!!! abstract "Architectural Update"
    *Historical Note:* This post refers to Zenzic as a "linter". As the system evolved, its capabilities expanded far beyond surface-level linting. Zenzic is now officially classified as a **Deterministic Document Integrity Engine for Markdown/MDX graphs**. Read the [latest documentation](https://zenzic.dev/) for current architectural capabilities.

Zenzic emerged as a systems response to a recurring pattern across code reviews and CI incidents: documentation quality pipelines were improving locally but degrading structurally over time. The pipeline was shipping checks, not guarantees — collecting signals, not preserving architecture.

<!-- more -->

This deep dive is for software architects and technical stakeholders who want to understand why architecture matters below the changelog line. The central claim of Zenzic is straightforward: zero-config should not mean zero-governance. It should mean deterministic defaults, explicit contracts, and interfaces that remain machine-readable under pressure.

The architecture came from five converging fronts: context fragmentation in complex repositories, dynamic-route ambiguity in static analysis, regex safety risk under adversarial inputs, deployment parity drift between local and CI, and governance blind spots that traditional SSG checks never model.

---

## 1) The Fragmentation Problem: When Context Stops Scaling

The initial symptom looked small: architectural decisions became less reliable during long-lived maintenance sessions. As the instruction corpus and policy body grew, operational consistency dropped. Contributors would correctly apply one rule while violating another that had already been established in the same architectural cycle.

At first glance, this looked like a documentation quality issue. It was not. It was an information scalability issue.

The internal project specification corpus had grown into a dense operational memory: naming rules, historical exceptions, governance gates, invariants, release constraints, and adapter-level contracts. Human readers can often navigate this through intent and pattern recognition. Automation systems cannot guarantee stable retrieval under long, mixed-priority context.

The result was a class of subtle regressions:

- Correct syntax, wrong contract tier.
- Correct code, stale policy semantics.
- Correct diagnostics, incomplete provenance.

This forced a design decision. Instead of pushing more monolithic text into workflows, context was split into deterministic artifacts that can be requested on demand.

That decision had two outputs:

- **Independent structural context tooling**, for repository cartography.
- **Zenzic JSON surfaces**, as machine-facing truth exports for routes and codes.

In practice, this changes the operating model from "read everything, hope for retention" to "request only the contract you need, exactly when needed."

For deterministic automation workflows, this is decisive. Systems no longer parse long prose to infer architecture. They query canonical interfaces.

---

## 1.5) Shift-Left Metrics You Can Verify Yourself

Performance claims are only useful if readers can reproduce them.

To verify Zenzic timing on your hardware, run the same checks locally and read the footer that Zenzic prints natively at the end of each run. The footer includes both elapsed duration and throughput.

Example footer:

```text
standalone • 20 files (14 docs, 6 assets) • 0.8s • 38 files/s
```

Recommended sequence:

```bash
zenzic check references docs/
zenzic check links docs/
zenzic check all docs/
```

For each run, record:

- elapsed duration (`0.8s` field),
- throughput (`38 files/s` field),
- scanned file scope (file count and mode).

This provides a hardware-specific baseline without synthetic benchmarking.

---

## 2) Virtual Site Map and Reverse Mapping: Solving Dynamic Routes Without Running Node.js

Dynamic routes are where traditional static linters lose clarity.

In Docusaurus, a route like `/blog/tags/python/` may not correspond to a physical Markdown file. It is generated from frontmatter metadata spread across multiple source files. Likewise for paginated indexes and author pages. A filesystem-only linter sees no file, concludes "broken link," and emits false positives.

Build engines can resolve this because they execute generation logic. But that happens late, is expensive, and does not produce source-level diagnostics suited to pre-commit loops.

Zenzic resolves this using the **Virtual Site Map (VSM)** with reverse mapping invariants.

At a high level:

1. Parse source Markdown and adapter metadata.
2. Build canonical route entries, including generated virtual routes.
3. Require each virtual route to carry non-empty `source_files` provenance.
4. Reject route records that cannot be traced to physical origin.

This is not heuristic URL guessing. It is a contract.

```python
@dataclass(frozen=True)
class VirtualRoute:
    url: str
    source_files: frozenset[str]

    def __post_init__(self) -> None:
        if not self.source_files:
            raise ValueError("virtual route without provenance is invalid")
```

The pay-off is diagnostic quality. When a generated route fails, Zenzic can point to concrete source origins and frontmatter context instead of returning generic route-not-found output.

Example machine output:

```bash
zenzic inspect routes --json
```

```json
{
  "route": "/blog/tags/python/",
  "kind": "tag",
  "status": "virtual",
  "source_files": [
    "blog/2026-05-01-v080-roadmap.md",
    "blog/2026-05-07-quartz-retrospective.md"
  ],
  "frontmatter_keys": ["tags", "slug", "authors"]
}
```

Now the error loop becomes actionable:

- you know the failing route,
- you know which files generate it,
- you know which frontmatter fields drive generation.

No Node.js execution is required to get this answer. That is the mathematical core of the Zenzic route model.

---

## 3) Security and ReDoS: The Incident Avoided by Design

Every documentation scanner eventually faces regex complexity risk. The usual implementation path is Python's standard `re` module. It is convenient, familiar, and dangerous under adversarial patterns because catastrophic backtracking can explode runtime.

In a benign repository this may look harmless. In CI at scale, under untrusted or malformed content, this becomes a denial-of-service vector.

The architectural response treated this as a systems boundary problem, not a style refactor.

The Zenzic solution is an **Anti-Corruption Layer (Facade)** around regex operations. Contributors keep a simple internal API. The runtime backend is enforced to use RE2 semantics for linear-time matching where policy requires determinism.

```python
from zenzic.core import regex

def contains_secret(line: str) -> bool:
    # contributor-facing API stays stable
    return regex.search(SECRET_PATTERN, line) is not None

```

This design gives us three guarantees at once:

- **Complexity bound:** matching remains predictable, avoiding catastrophic backtracking classes.
- **Policy enforcement:** unsafe or unsupported patterns fail early at load/validation boundaries.
- **DX continuity:** contributors use one internal import path, not backend-specific code scattered across modules.

In architectural terms, the facade prevents dependency leakage. The domain model talks to a local contract; backend details stay behind the boundary. That is why security semantics can be hardened without destabilizing contributor workflows.

---

## 4) Four Gates in CI/CD: Security as a Supply Chain, Not a Single Check

Many teams still treat documentation quality as a final build concern. Zenzic models it as a layered gate system where each stage narrows risk before it becomes expensive.

The gate model has four levels:

1. **IDE Gate**
2. **Pre-Commit Gate**
3. **Pre-Push Gate**
4. **GitHub Actions Gate**

The purpose is not duplication. The purpose is risk distribution.

- The IDE catches immediate authoring drift.
- Pre-commit blocks local bad states before history contamination.
- Pre-push enforces integration-level checks before remote divergence.
- GitHub Actions provides reproducible, shared enforcement at repository boundary.

The implementation hinge is the `justfile`. It is not a convenience wrapper; it is the parity contract.

```make
verify:
    uvx pre-commit run --all-files
    uvx nox -s tests
    uvx nox -s verify-codes-parity
```

When local and remote run the same orchestration surfaces, policy drift shrinks. This is **Sovereign Parity**: the same rules, same tooling strata, same exit semantics, regardless of execution location.

That matters for governance and auditability. A failed gate must mean the same thing everywhere, or the gate is procedural theater.

---

## 5) The Namespace Contract: Why Tier Boundaries Changed the System

Before Zenzic, code families existed but ownership semantics were still easy to blur in real contribution flows. A policy rule could be discussed like a core invariant. A plugin rule could be treated like a frozen security guardrail.

The namespace contract was formalized to prevent that bleed.

- **Core**: engine invariants.
- **Governance**: project policy and lifecycle rules.
- **Plugin**: third-party extension surfaces.
- **Custom**: local project constraints.

This matters because suppression semantics and enforcement expectations are tier-dependent by design. Zenzic additionally formalizes immutable surfaces such as `FROZEN_CODES`, `NON_SUPPRESSIBLE_CODES`, and `PLUGIN_FORBIDDEN_EXITS` so that security findings cannot be casually reclassified into optional style noise.

Security findings are not suggestions. They are enforcement events.

---

## 5.5) Adapter Refactoring: From Protocol Flexibility to ABC Contracts

v0.8.0 changed the adapter layer from permissive structural typing to explicit runtime contracts.

In the v0.7 line, adapter compliance relied on a `Protocol` surface plus runtime duck-typing checks. That model was flexible but late-failing: missing capabilities could escape until scan or validation paths were already running.

In v0.8, the contract is a concrete `BaseAdapter` Abstract Base Class with required abstract methods and factory-level subclass enforcement. Invalid adapter implementations now fail at instantiation time, not in mid-pipeline execution.

| Dimension | v0.7 Behavior | v0.8 Current Behavior |
|:--|:--|:--|
| Contract type | Structural `Protocol` + duck typing | Nominal `ABC` (`BaseAdapter`) |
| Capability checks | Mixed optional probing | Mandatory abstract methods |
| Failure point | Late (scan/validate path) | Early (factory construction) |
| Core coupling | Scanner-side engine probes | IoC-injected callbacks and roots |

This refactor also applies Inversion of Control to the scanner boundary. The Core scanner no longer discovers engine details internally. Adapter context is resolved once by orchestration and injected as explicit callbacks and content roots, keeping the scanner engine-agnostic.

Logical flow:

```text
BuildContext + repo_root
  -> get_adapter(...)
  -> inject adapter callbacks + discovered roots
  -> scanner/validator execute without engine discovery logic
```

MkDocs coverage was upgraded in the same cycle: multi-root discovery is now native in `MkDocsAdapter`, including recursive monorepo include traversal. Additional roots are mounted into the same VSM and reference-validation perimeter, so external docs trees no longer require manual wiring.

---

## 6) Eradicating Inline Noise: Directory Policies

Every governance system eventually encounters a legitimate exemption problem. Brand-term checks are essential for catching stale references in active documentation. But release blogs are historical artifacts. Enforcing `Z601` (obsolete brand term) against a blog post that intentionally names the old release identifier is not quality enforcement — it is false positive noise.

Before `directory_policies`, the only escape was an inline suppression comment scattered across every affected line:

```mdx
`<!-- zenzic:ignore: Z601 historical release -->`
Quartz was the internal code name for v0.6.0.
`<!-- zenzic:ignore: Z601 historical release -->`
The Obsidian milestone closed the legacy adapter contract.
```

This approach accumulates debt. Inline suppressions count against the `suppression_cap`. Each file that writes its own inline escapes consumes one audit slot. At `suppression_cap = 10`, a fleet with many historical blog posts can exhaust the cap through legitimate exemptions, leaving no headroom for actual suppression abuse.

The structural fix introduced in v0.8.0 is `directory_policies`: a governance-level TOML contract that grants zero-debt exemptions to named path patterns.

```toml title=".zenzic.toml"
[governance]
suppression_cap = 10
suppression_cap_fail_hard = true

[governance.directory_policies]
"blog/**"                         = ["Z601"]  # historical release posts: brand terms are intentional
"explanation/mineral-path.md"    = ["Z601"]  # SSOT codename registry (EN)
"it/explanation/mineral-path.md" = ["Z601"]  # SSOT codename registry (IT)
```

With this configuration in place, the blog posts become clean:

```mdx
Quartz was the internal code name for v0.6.0.
The Obsidian milestone closed the legacy adapter contract.
```

No inline tags. No suppression comments. No debt. The policy exemption is declared once at the governance contract level, not repeated across every affected line.

When Zenzic applies a policy exemption during a standard scan, findings in those paths are dropped silently; the `[POLICY_EXEMPTION]` label is emitted only in `--audit` mode, giving reviewers a complete, centralized record of what was exempted and under which pattern. This preserves auditability without hiding the signal.

The hierarchy that emerges is deliberate:

1. **Non-suppressible codes** (`NON_SUPPRESSIBLE_CODES`) — security findings that cannot be overridden by any mechanism.
2. **Directory policies** — governance-level zero-debt exemptions declared in `.zenzic.toml`.
3. **Inline suppressions** — per-line escape hatches, counted against the cap and logged.

Zero-debt means the suppression cap is preserved for genuine edge cases, and the governance contract remains the authoritative source of intent.

---

## Why This Is a Zero-Config Ecosystem, Not a Zero-Policy Tool

Zero-config often gets misread as "minimal architecture." In Zenzic, zero-config means deterministic defaults with explicit contracts that remain inspectable.

That is why JSON inspection surfaces and tiered code contracts are first-class in the current architecture:

- They reduce ambiguity for humans.
- They reduce context burden for automation.
- They stabilize governance across contributors, integrations, and CI.

From an architectural perspective, Zenzic is less about adding checks and more about reducing interpretive entropy.

---

## Closing Perspective

The old mental model said: "if the site builds, documentation quality is acceptable."

Zenzic rejects that model.

A successful build can still hide leaked credentials, governance drift, unresolved virtual-route provenance, and policy regressions invisible to render pipelines. Build engines remain essential. They are just not sufficient as documentation integrity systems.

The system proves a different path:

- deterministic source-first analysis,
- machine-consumable architectural truth,
- linear-time security boundaries,
- and sovereign parity from local workstation to remote CI.

That is what a zero-config ecosystem looks like when engineering contracts are treated as public infrastructure, not internal folklore.
