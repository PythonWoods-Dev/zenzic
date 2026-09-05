---
title: "Deterministic Tooling & The Pre-Commit Distribution Model"
slug: deterministic-tooling-and-pre-commit
date: 2026-09-05 15:00:00
draft: true
authors:
  - pythonwoods
description: >
  Why global tool installation fails in professional documentation engineering,
  and how Zenzic's canonical distribution hierarchy guarantees zero environment
  contamination, lockfile reproducibility, and sub-50ms local verification.
categories:
  - Architecture
  - Best Practices
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

> **A quality policy is only deterministic if the mechanism that executes it is deterministic too.**

**Deterministic enforcement requires deterministic distribution.** [Specification-Driven Development](2026-08-22-zenzic-v0310-specification-driven-development.md) only holds if the tool enforcing it is the same tool, at the same version, everywhere it runs.

There is a common pattern in engineering tooling.

A team defines a quality rule, documents it, installs a command-line tool, and adds the command to the development workflow.

At first, everything looks fine. Then the team grows. One developer upgrades the tool. Another keeps an older installation. CI runs a third version. A fourth contributor uses an isolated environment. The same repository now has several interpretations of the same quality policy.

Nothing is obviously broken. The tool works. The configuration is correct. The checks still run.

Yet the quality gate is no longer deterministic.

This is the distribution boundary problem. It is easy to mistake it for an installation problem. It is actually a governance problem.

<!-- more -->

---

## The rule is not the executable

Suppose a repository defines a policy:

> Every documentation change must pass the project's static analysis checks.

The policy sounds precise. But what exactly does "the project's static analysis checks" mean? Does it mean the version installed globally on a developer's laptop? The version used by CI? The version referenced in a lockfile? The latest version available on the package index?

If those answers differ, the policy is underspecified operationally. The repository may contain one policy definition while the organization executes several implementations of it. That distinction becomes increasingly important as static analysis moves beyond formatting and link checking into security, topology, governance, and specification validation.

## Why global installation is attractive

Global installation has a legitimate advantage: it is frictionless. A developer can install a tool once and run it from anywhere. That is useful when evaluating a tool for the first time, and for occasional investigations where reproducibility is not the primary concern.

The problem appears when a global installation becomes an implicit dependency of a team workflow. A global executable has state outside the repository. Its version is controlled by the workstation. Its dependencies are controlled by the workstation. Its upgrade schedule is controlled by the workstation. The repository cannot fully describe the environment in which the command will run.

That is precisely the property that makes global installation a poor foundation for deterministic enforcement.

## Four kinds of drift

The resulting failures usually fall into four categories.

### 1. Version drift

Different users run different releases:

```text
Developer A     → 0.29
Developer B     → 0.30
CI              → 0.31
```

The difference may be harmless. It may also include new rules, changed severity, parser fixes, changed defaults, new finding codes, or changed exit-code behavior. The important point is that the organization no longer knows which implementation represents the policy during local development.

### 2. Dependency drift

A Python command-line tool can depend on other Python packages. If it is installed into a shared environment, those dependencies coexist with unrelated project dependencies — creating opportunities for version conflicts. A documentation analyzer should not need to compete with the project's runtime environment for control over a dependency such as a parser, validation library, or other transitive package.

The clean architectural boundary is simpler:

```text
Project runtime
       │
       ├── application dependencies
       └── application tooling

Documentation analyzer
       │
       └── its own dependencies
```

The analyzer does not need to become part of the application runtime merely because both happen to use Python. The current Zenzic installation guidance explicitly recommends `uv` or `uvx` for isolated execution and notes that the linting environment does not need MkDocs, Material for MkDocs, or build plugins, because Zenzic reads their configuration rather than executing the build system.

### 3. Policy drift

Suppose a new rule is introduced. CI starts enforcing it. The repository configuration describes it. A contributor who has not upgraded their local tool does not see the finding. The contributor pushes the change. CI rejects it.

Nothing is wrong with CI. But the feedback loop has moved from the developer's machine to the remote pipeline. The result is avoidable friction. A deterministic quality gate should ideally identify a defect as close as possible to the point at which the defect is introduced.

### 4. Execution drift

Even with the same version, tools can be executed under different conditions. One environment may have access to the network. Another may be offline. One invocation may run strict mode. Another may use defaults. One developer may run the full repository check. Another may run only a subset.

The tool is technically the same. The enforcement workflow is not.

This is why deterministic tooling cannot be reduced to version pinning alone. Version is one part of the execution contract.

## The distribution boundary

A useful way to reason about tooling is to identify where the executable crosses into the development workflow. There are three practical boundaries.

```text
                 Stronger repository control
                         ↑
                         │
        Commit boundary  │  Pre-commit
                         │
        Project boundary │  Lockfile / project environment
                         │
        User boundary    │  Global installation
                         │
                         ↓
                 Greater local autonomy
```

These are not mutually exclusive installation methods. They are different enforcement models.

## Boundary 1: The commit

The strongest local enforcement boundary is the commit. A pre-commit hook executes before a change is recorded — the contributor gets feedback while the change is still local, before it becomes someone else's problem.

Pre-commit also provides an isolated execution environment for hooks. This gives the repository control over more of the execution context without requiring the documentation analyzer to become a dependency of the application's runtime.

Zenzic explicitly supports pre-commit use, and its CLI includes a dedicated `guard` command with a staged-file mode designed for the fast pre-commit path. The tool can also generate or update a native pre-commit hook definition through `zenzic guard init`.

There is a failure mode worth naming before going further, because it undoes everything above and looks like nothing at all: **a declared hook is not an installed hook.** `.pre-commit-config.yaml` is a description of intent. What actually runs is whatever is in `.git/hooks/`, and that directory is populated by `pre-commit install` — a step no clone performs on its own. A contributor who clones the repository and starts committing has the full configuration and none of the enforcement.

Nothing signals this. The configuration is present and valid, the commits succeed, and the checks that were supposed to run simply do not. The gate is not bypassed; it was never in the path. This happened in Zenzic's own repository: eighteen hooks declared, `.git/hooks/` empty, and an entire working session's commits recorded without a single check running. It surfaced only when the hooks were finally installed and the very next commit was blocked by two genuine type errors — in a change whose author had run the linter and not the type checker, which is exactly the asymmetry the hook exists to remove.

The practical consequence is that a repository relying on pre-commit needs a check that the hooks are installed, not only that they are configured. That check has to live somewhere that runs regardless — a task-runner recipe used in normal work, or a test-session fixture — because a hook cannot verify its own installation: if it were installed enough to run, the condition it is checking for would already be false.

A minimal conceptual workflow looks like this:

```text
edit
  ↓
git add
  ↓
pre-commit
  ↓
documentation checks
  ↓
commit
```

The important property is not the particular framework. It is the boundary. The quality check occurs before the change crosses into shared history.

## Boundary 2: The project

The second boundary is the project environment. Here, the analyzer is declared alongside the project's development tooling and resolved through the project's dependency-management mechanism. The repository can then define which version is required, which dependency graph is acceptable, how the environment is reproduced, and how CI obtains the same tooling.

This is particularly useful for projects that already use a lockfile-based Python workflow. The advantage is not that a lockfile magically makes every execution identical. It is that the repository becomes the authoritative source for dependency resolution instead of every developer's workstation.

The distinction is significant. A global installation says: *my machine has this tool.* A project dependency says: *this project requires this tool.* Only the second statement is directly relevant to repository governance.

## Boundary 3: Ephemeral execution

The third boundary is useful precisely because it does not require permanent installation. `uvx` can fetch Zenzic into an isolated environment, execute it, and discard that environment after the command finishes:

```bash
# One-off local test only — pin the version for anything beyond a single ad hoc run
uvx zenzic@0.30.0 check all
```

This is particularly useful when evaluating an unfamiliar repository — there is no need to modify the project's Python environment just to run an audit. The public Zenzic tutorial uses this model as its starting point and describes it as an installation-free path for auditing a repository. The installation documentation also identifies `uvx` as appropriate for one-off jobs and CI workflows that do not already have a project installation phase.

This is an important distinction from a global install. Ephemeral execution provides convenience without turning the workstation's persistent environment into part of the repository's quality contract — but convenience is not the same thing as reproducibility. An unpinned `uvx zenzic` invocation still floats with whatever release is latest at execution time, which is fine for a single exploratory run and not fine for anything repeated. As soon as the same command is meant to produce the same result twice, it needs a version pin — see "Pinning is necessary, but not sufficient" below.

## These boundaries are complementary

The three models should not be understood as a contest in which one must eliminate the others. A healthy workflow can use all three:

```text
Evaluation
    ↓
uvx
    ↓
Project adoption
    ↓
project dependency or pre-commit
    ↓
Local enforcement
    ↓
pre-commit
    ↓
Remote enforcement
    ↓
CI
```

Each stage serves a different purpose. Ephemeral execution minimizes the cost of trying a tool. Project management establishes a reproducible environment. Pre-commit provides early local enforcement. CI provides an independent remote gate.

The mistake is not using global or ephemeral execution. The mistake is confusing an exploratory execution model with an enforcement model.

## Local and remote gates should agree

A common CI pattern is:

```text
developer
    ↓
local checks
    ↓
pull request
    ↓
CI checks
```

This only works well if the two checks are substantially equivalent. Otherwise CI becomes a second, unrelated implementation of the quality policy.

Zenzic's own workflow moves through progressively stronger verification boundaries — pre-commit, pre-push, and CI. Keeping the local and remote paths aligned is the goal rather than a solved problem: a check that runs in one and not the other is a gap, and gaps of that kind accumulate quietly, because nothing fails when a check simply is not there. The principle generalizes beyond Zenzic: the closer local and remote enforcement are, the more useful local feedback becomes. If local verification and CI use different versions, configurations, or rule sets, developers are effectively debugging the CI environment rather than validating their changes.

## Pinning is necessary, but not sufficient

It is tempting to summarize deterministic tooling with a single rule:

> Pin the version.

Pinning is important. It prevents an unbounded dependency on whatever happens to be latest at execution time. But version pinning does not solve every source of divergence.

A deterministic workflow also needs clarity about configuration, dependency resolution, execution mode, network behavior, scope, exit-code semantics, and local versus CI invocation. For example, Zenzic's `check all` supports explicit modes such as `--strict`, `--ci`, `--offline`, `--no-external`, and `--quiet`. These flags affect how the check behaves, which means a workflow that cares about reproducibility should define the invocation rather than relying entirely on defaults.

This applies to every example in this article, including the ones above: `uvx zenzic@0.30.0` and the `.pre-commit-config.yaml` `rev:` are shown pinned here for exactly this reason. A `uvx zenzic check all` with no version suffix is acceptable only for a single, throwaway evaluation run — the moment that command is meant to be repeatable, or run by more than one person, it needs the same pin as everything else.

The general principle is:

> Pin the tool, define the policy, and define the execution contract.

## Why isolation matters

Isolation is often described as a convenience. It is better understood as a correctness mechanism.

Suppose a documentation analyzer needs one version of a dependency while the application requires another. Installing both into the same environment creates an unnecessary coupling. The application and the analyzer have different responsibilities — they should not have to share a runtime merely because they happen to be used in the same repository.

Zenzic's documented model reflects this distinction: it reads documentation and build configuration as static input and does not execute the build engine or its plugins during analysis. That means a project does not need to install the complete documentation build stack merely to perform static analysis. The smaller the analysis environment, the smaller the dependency surface that needs to be reproduced.

## Fast checks belong at the earliest boundary

Not every analysis should necessarily run before every commit. This is where execution scope becomes important.

A fast security or credential check can be appropriate for the commit boundary. A more expensive whole-repository topology analysis may be better suited to pre-push or CI. The principle is not "run everything everywhere." It is: run the right level of verification at the earliest boundary where its cost is justified.

Zenzic's `guard scan --staged` is an example of this distinction: the command can restrict scanning to staged Markdown/MDX files for the fast pre-commit path, while `check all` performs the broader validation suite.

This makes the enforcement model more practical. A quality gate that adds negligible friction is easier to keep enabled.

## Quiet success is part of the workflow

A quality gate should also respect the environment in which it runs. Interactive terminal output can be useful for developers. The same output can become noise in a pre-commit hook or CI log.

Zenzic's CLI therefore exposes a quiet mode for automated contexts, and its documented design includes a silent-on-success contract for automated gates. This may appear minor. It is not — developer experience affects whether a quality gate remains enabled. A theoretically perfect gate that produces unnecessary output, takes too long, or interrupts unrelated workflows will eventually be bypassed. Friction is therefore an architectural concern.

## Security changes the boundary

Security checks deserve a slightly different treatment. A credential leak is not an ordinary documentation finding — once a secret reaches a repository, the appropriate response may involve rotation and history cleanup rather than merely correcting a Markdown file.

Zenzic separates credential findings from ordinary quality findings. Its credential scanner is designed to run across documentation content, including fenced code blocks, and security findings use a dedicated exit-code contract. This is another reason to place lightweight security checks close to the commit boundary — the earlier a credential is detected, the less likely it is to propagate into shared history.

Remote CI remains necessary because local hooks can be bypassed. Zenzic's GitHub Action documentation describes a separate guard-scan step that can provide defense in depth when contributors bypass pre-commit with `git commit --no-verify`.

The resulting model is not trust in one gate. It is layered enforcement.

## What about global installation?

Global installation still has a place. It is useful when evaluating a tool, experimenting locally, debugging a workstation, running occasional commands, or working outside a repository-managed environment.

The mistake is assigning it a responsibility it cannot reliably fulfill.

A global binary is a user convenience. A repository-managed dependency is a project requirement. A pre-commit hook is an enforcement mechanism. An ephemeral, pinned `uvx` invocation is a low-friction execution mechanism. Those are different roles.

## A practical adoption path

Teams do not need to redesign their tooling architecture before trying deterministic execution. A low-friction migration can happen in stages.

### Stage 1 — Run without installing

Use an ephemeral command against the existing repository:

```bash
# Discovery only — an unpinned run is acceptable here, but not beyond this stage
uvx zenzic check all
```

The goal is discovery. No project dependencies need to be changed. No build environment needs to be modified. The current documentation state can simply be observed.

### Stage 2 — Establish a baseline

Once the team understands the findings, establish a quality baseline:

```bash
zenzic score --save
```

and regression comparison through:

```bash
zenzic diff --threshold 5
```

The latter allows a project to reject regressions without requiring every existing defect to be fixed immediately. This is an important adoption pattern — a new quality gate does not have to turn legacy debt into a migration blocker. It can first prevent the situation from getting worse.

### Stage 3 — Move enforcement closer to the commit

Introduce the relevant checks into pre-commit. Start with the checks that provide the highest signal at the lowest cost — credential scanning is an obvious example. Other checks can be assigned to later workflow stages according to their cost and purpose.

### Stage 4 — Reproduce the policy in CI

CI should provide an independent enforcement point. The goal is not to create a different policy. The goal is to verify that the same repository contract holds on a clean runner.

### Stage 5 — Manage the environment explicitly

Where the project already has a dependency-management strategy, decide whether the analyzer belongs in that environment or should remain isolated. The answer depends on the repository. What should not be left implicit is the execution contract — including the version pin.

## The goal is not maximal automation

There is a subtle danger in discussions about quality gates. Once teams discover that something can be automated, they may attempt to automate everything. That is not the goal.

The purpose of deterministic tooling is to remove ambiguity from checks that are already objective. A machine is well suited to questions such as: does this file exist? Does this link resolve? Is this value permitted? Is this credential pattern present? Is this section missing? Has the quality score regressed? Does this document satisfy the configured structural contract?

A machine is less suited to questions such as: is this architecture appropriate? Is this explanation useful to a new user? Is this requirement actually necessary? Is the trade-off acceptable?

The first category benefits from deterministic enforcement. The second still requires engineering judgment. The best workflow keeps those responsibilities separate.

## Distribution is part of the quality model

Once a repository treats documentation as an engineering artifact, its quality model has two dimensions: the policy itself, and how that policy reaches the people and systems expected to enforce it.

```text
Policy
  │
  ├── Configuration
  │
  ├── Tool version
  │
  ├── Dependencies
  │
  └── Execution mode
          │
          ↓
     Enforcement
          │
          ├── Developer
          ├── Pre-commit
          ├── Pre-push
          └── CI
```

If any of these components is allowed to drift without an explicit decision, the effective policy can drift with it. This is why distribution architecture belongs in discussions about quality engineering. It is not an installation footnote. It is part of enforcement.

## The commit boundary is a useful default

The commit is a particularly useful boundary because it is both early and repository-specific. The change is known. The repository is known. The policy is known. The feedback can be immediate.

Pre-commit therefore provides a natural place for lightweight deterministic checks, while project environments and CI provide additional layers of reproducibility and independent verification. This does not mean every check must execute at commit time — it means that the workflow should deliberately choose where each check belongs rather than allowing the location to emerge accidentally from installation instructions.

## Determinism starts before CI

It is common to think of deterministic tooling as a CI concern. By the time a check reaches CI, however, the most useful opportunity for feedback may already have passed.

A developer who discovers a violation before committing can fix it immediately. A developer who discovers it after pushing has already created a remote workflow. A reviewer who discovers it after reviewing the pull request has spent human attention on something that a machine could have identified earlier.

A deterministic local gate therefore reduces not only technical drift but also process friction. That is the real value of moving enforcement toward the commit boundary.

## The broader principle

Documentation engineering is increasingly moving toward the same practices long established for source code: explicit policies, reproducible environments, static analysis, automated quality gates, regression tracking, layered verification, and machine-readable diagnostics.

That evolution creates a simple requirement: the tool executing the policy must itself be part of the reproducible system. Otherwise the repository says one thing while the developer environments execute another.

The solution is not to ban global tools. It is to give each distribution mechanism the role it is good at.

Use ephemeral execution when trying a tool should require almost no commitment. Use project-managed dependencies when the tool belongs to the project's reproducible environment. Use pre-commit when a check should become part of the commit boundary. Use CI as the independent remote gate. And keep the policy itself in the repository.

The important boundary is not between one installation command and another. It is between **convenient execution** and **deterministic enforcement**.

Once that distinction is explicit, the architecture becomes much simpler:

> **The repository defines the policy.
> The environment reproduces the tool.
> The commit catches problems early.
> CI verifies the result independently.**

For the specification-level failure modes this distribution model exists to guard against — missing table columns, invalid cell values, scrambled heading order, and broken traceability — see [Zenzic v0.31.0: Specification-Driven Development & AI Knowledge Graph Integrity](2026-08-22-zenzic-v0310-specification-driven-development.md).
