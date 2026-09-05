---
description: "How Zenzic reduces documentation risk, removes manual QA loops, and enforces deterministic CI/CD quality gates."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Why Zenzic — Risk Prevention and Deterministic Quality Gates

Zenzic is a Deterministic Document Integrity Engine for Markdown/MDX graphs. It operates on raw source files — never the generated output — so it works with any build engine (MkDocs, Zensical, or others via the adapter system). It detects broken links, orphan pages, placeholder stubs, unused assets, and leaked credentials before the build runs.

Zenzic exists to prevent documentation defects from entering the main branch. The objective is
operational: block regressions before release, reduce security exposure, and keep CI outcomes
deterministic.

---

## Business Value

Three concrete outcomes justify running Zenzic in CI: fewer production defects, less manual
review time, and repeatable, auditable gate behavior.

### 1. Risk Reduction

Zenzic prevents high-impact documentation failures before deployment:

- broken internal links that become production 404s,
- leaked credentials in Markdown or code blocks,
- navigation or topology inconsistencies that hide critical pages.

For public repositories, credential detection (Z2xx) is a direct control against accidental
secret exposure.

### 2. Time Savings

The quality gate automates checks that are often done manually during review.

Correct framing: **the automated quality gate prevents documentation debt from entering the main
branch, removing manual review loops for broken links.**

Teams stop spending review cycles on repetitive defects and can focus on content quality.

### 3. Reliability

Reliability means repeatable outcomes from identical inputs. Zenzic enforces deterministic
analysis and deterministic exit codes so CI behavior is stable across runs and environments.

---

## Defence Trinity {#defence-trinity}

Three independent layers defend a repository's integrity, each with its own gate behavior.

### Link Integrity (Z1xx)

Internal links, anchors, and route references are validated before build. This prevents runtime
navigation failures from reaching users.

### Credential & Forbidden-Term Detection (Z201/Z204/Z205) {#credential-scanner}

The scanner checks each file for known credential patterns, project-specific forbidden terms, and
forbidden URL schemes. These three codes are fail-closed, non-suppressible, and exit 2
unconditionally — the strictest gate in the system.

### Path Traversal Safety (Z202/Z203) {#path-traversal-guard}

Path traversal and unsafe path resolution are blocked. Both codes are non-suppressible, but their
exit behavior differs: an ordinary boundary violation (`Z202`) is a plain quality finding, exit 1;
a traversal targeting an OS system directory (`Z203`) is a fatal security incident, exit 3.

---

## Deterministic Execution Model {#three-pillars}

Zenzic's determinism rests on the same [Three Pillars](../developers/explanation/governance/index.md#the-supreme-law-the-three-pillars) that govern the whole project:

1. **Lint the Source, Not the Build.**
2. **Zero Subprocesses.**
3. **Pure Functions First.**

This model keeps the same repository state tied to the same finding set and the same gate result.

---

## CI Gate Semantics

- **Exit 0**: no blocking findings.
- **Exit 1**: quality findings block merge.
- **Exit 2**: credential/security finding.
- **Exit 3**: path traversal guard violation.

The DQS flat-cost model keeps suppression debt explicit: each suppression contributes a fixed
penalty, so score movement is predictable and reviewable.

---

## Use Cases

- **B2B monorepo maintenance**: enforce consistent doc quality across multiple services.
- **API portal validation**: prevent broken route references and hidden navigation regressions.
- **Docs-as-code CI pipelines**: block regressions early with deterministic gate behavior.

---

## See Also

- [Core Architecture](./architecture.md)
