---
title: "Markdown Is Production Code: Why We Built Zenzic"
slug: markdown-is-production-code-why-we-built-zenzic
date: 2026-08-08
authors:
  - pythonwoods
description: >
  Why we built Zenzic to treat documentation integrity as a deterministic CI
  property, combining graph analysis, security scanning, structured diagnostics,
  and reproducible quality gates for Markdown and MDX.
categories:
  - Engineering
  - Documentation
  - Security
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

We built Zenzic because we kept seeing the same problem: a documentation repository could be technically “green” while the documentation itself was already broken.

A build can succeed while an internal link points to a file that no longer exists. A page can remain in the repository while no navigation path reaches it. An anchor can become invalid after a heading is renamed. An image can disappear while the Markdown still references it. A code example can contain a live credential that gets copied into a public repository.

The build can still pass.

The deployment can still complete.

The defect is discovered only when a user follows the broken path—or when an exposed credential is abused.

We decided that this was the wrong model.

**We built Zenzic to treat documentation integrity as a property that can be tested before a change reaches the main branch.**

Zenzic is a deterministic document-integrity engine for Markdown/MDX graphs. It analyzes raw documentation source, builds a model of its relationships, and reports structural, quality, and security findings with file-and-line precision.

Our objective is operational:

> Prevent documentation defects from entering the main branch.

That means reducing production risk, removing repetitive manual review loops, and making CI outcomes deterministic.

<!-- more -->

# Markdown Is Production Code
## Why we built Zenzic to make documentation integrity a deterministic CI gate

We built Zenzic because we kept seeing the same problem: a documentation repository could be technically “green” while the documentation itself was already broken.

A build can succeed while an internal link points to a file that no longer exists. A page can remain in the repository while no navigation path reaches it. An anchor can become invalid after a heading is renamed. An image can disappear while the Markdown still references it. A code example can contain a live credential that gets copied into a public repository.

The build can still pass.

The deployment can still complete.

The defect is discovered only when a user follows the broken path—or when an exposed credential is abused.

We decided that this was the wrong model.

**We built Zenzic to treat documentation integrity as a property that can be tested before a change reaches the main branch.**

Zenzic is a deterministic document-integrity engine for Markdown/MDX graphs. It analyzes raw documentation source, builds a model of its relationships, and reports structural, quality, and security findings with file-and-line precision.

Our objective is operational:

> Prevent documentation defects from entering the main branch.

That means reducing production risk, removing repetitive manual review loops, and making CI outcomes deterministic.

## Documentation can be green while being broken

Technical documentation is often treated as editorial content: useful, important, and reviewed when someone has time.

We think that model breaks down once documentation becomes part of a software product.

Documentation contains links, routes, anchors, navigation contracts, configuration examples, shell commands, credentials, asset references, and deployment instructions. These are not merely pieces of prose. They are relationships and dependencies.

A repository can compile successfully while those relationships are already invalid.

That makes documentation drift particularly dangerous because it is usually silent.

A page can continue to exist while no navigation path reaches it. A link can point to a file removed months earlier. An anchor can become invalid after a heading is renamed. An image can disappear while the Markdown still references it. A code block can contain a credential that is copied into a public repository.

Traditional Markdown linting addresses only part of this problem. It can enforce formatting, heading style, or whitespace rules, but it generally does not understand the documentation repository as a connected graph.

We built Zenzic around a different model:

> **Documentation is production code.**

Once we treat it that way, questions about reachability, references, topology, assets, navigation, and security become testable properties rather than things we hope a reviewer notices.

## What we want to prevent

Our motivation for building Zenzic can be reduced to three outcomes: **risk reduction, time savings, and reliability**.

### Risk reduction

We want to prevent high-impact documentation failures before deployment.

That includes:

- broken internal links that become production 404s;
- missing anchors that break navigation;
- orphan pages that users cannot reach through the documentation structure;
- navigation inconsistencies that hide important content;
- missing or unused assets;
- credentials exposed inside Markdown or code blocks;
- unsafe paths and path traversal.

For public repositories in particular, credential detection is a direct control against accidental secret exposure.

### Time savings

A surprising amount of documentation maintenance consists of repetitive review work.

A reviewer notices a broken link.

Someone fixes it.

The pull request is updated.

The reviewer checks it again.

The same cycle happens for missing assets, malformed references, or other mechanical defects.

We wanted the quality gate to automate those checks so that human reviewers could focus on content quality, technical accuracy, and product decisions rather than repeatedly verifying mechanical relationships.

The goal is not to eliminate documentation review.

The goal is to eliminate review loops for defects that a machine can determine with certainty.

### Reliability

The third requirement is reliability.

For us, reliability means that identical source input should produce identical findings and an identical gate result.

If the repository has not changed, CI should not randomly pass on one run and fail on another.

That requirement is why determinism is not an implementation detail in Zenzic. It is part of the product.

## What Zenzic checks

Zenzic combines document integrity, topology, quality, and security checks in one analysis pass.

Our finding catalog includes checks such as:

- broken internal links and missing files;
- missing anchors;
- malformed or absolute paths;
- circular links and circular anchors;
- missing directory indexes;
- orphan pages and unreachable graph nodes;
- unused or missing assets;
- missing image alt text;
- navigation-contract violations;
- leaked credentials;
- path traversal;
- forbidden URI schemes;
- placeholder content and short pages;
- malformed frontmatter;
- heading hierarchy problems;
- obsolete brand terms;
- stale or dead suppressions;
- quality regressions against a saved baseline.

These checks operate at different levels.

Some findings can be determined from an individual source line. Others require us to understand the relationships between files, headings, links, assets, and navigation across the entire documentation repository.

That distinction is fundamental to how we designed Zenzic.

## A failure should point to the source

A quality gate is useful only if developers can act on its output.

We therefore report findings with the path, line number, and relevant source context. Instead of forcing a maintainer to search through a long CI log, the output identifies the exact location of the problem.

For example:

```text
docs/index.md:3:8 ✘ [Z104] './intro.md' not found in docs

    1 │ # Welcome
    2 │
    3 ❱ See the [intro page](./intro.md) for details.
       │ ^^^^^^^^^^^^^^^^^^^^^^^^^^^


The difference matters operationally.

“Documentation failed” is an interruption.

“This reference on line 3 points to a missing file” is an actionable task.

We use the same model for security findings:

SECURITY BREACH DETECTED

Finding: GitHub token detected
Location: docs/tutorial.md:42
Credential: ghp_************3456

Action: Rotate this credential immediately and purge it from repository history.


Secrets are redacted in diagnostic output while the pipeline receives a security-specific failure.

We consider precise diagnostics part of the quality gate itself. Detecting a defect is only half the job; the result also needs to make remediation obvious.

Markdown is also a security boundary

One of the decisions we made early was to treat documentation as an explicit security surface.

Documentation is full of examples:

export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...

github_token: ghp_...


These examples are often copied from real deployment sessions.

A developer may intend to redact a token and accidentally commit a live value. In a public documentation repository, that mistake can have immediate consequences.

Zenzic scans Markdown source line by line, including fenced bash and yaml blocks, for known credential patterns.

Security findings use a distinct exit code: exit code 2 is reserved for security events and is treated as non-suppressible.

We do not consider this a replacement for a repository-wide secret scanner.

Gitleaks or TruffleHog may still be appropriate for scanning the full Git history and all repository file types. Their scope is broader than documentation.

Our goal is different:

Treat documentation itself as an explicit security boundary.

This gives us a useful defence-in-depth model. A repository-wide scanner protects the repository broadly, while Zenzic protects the documentation pipeline specifically.

The Defence Trinity

We designed Zenzic around three defensive boundaries.

Link Integrity — Z1xx

Internal links, anchors, and route references are validated before the documentation build.

The objective is simple: prevent runtime navigation failures from reaching users.

Credential Leak Prevention — Z2xx

The scanner checks source files for known credential patterns, including credentials that appear inside documentation examples and fenced code blocks.

Security findings fail closed and immediately stop the pipeline.

Path and Topology Safety — Z202/Z203

Path traversal and unsafe path resolution are blocked.

Configuration and analysis must not be able to escape the repository boundaries they are supposed to inspect.

Together, these controls cover three different failure modes:

references  →  security  →  filesystem boundaries


We do not think these are interchangeable concerns. A documentation integrity system needs to reason about all three.

The graph behind the files

A documentation site is not merely a directory of Markdown files.

It is a graph.

Conceptually:

index.md
 ├── links to install.md
 ├── links to api.md#authentication
 └── references assets/architecture.png


Once we model the documentation this way, we can ask questions that a line-oriented linter cannot answer easily:

Does install.md exist?
Does the authentication anchor exist in api.md?
Is api.md reachable from the site navigation?
Is a page present but disconnected from the graph?
Is an asset referenced by any page?
Does navigation point to a page that the source graph cannot resolve?
Does the graph contain an unsafe path or a dead end?

This is why we describe Zenzic as a document-integrity engine, not simply another Markdown linter.

The distinction is important.

A traditional linter can ask:

“Is this line formatted correctly?”

We also need to ask:

“Does this line describe a relationship that actually exists?”

Source before generated output

We deliberately chose to analyze raw Markdown and MDX source rather than waiting for generated HTML.

This means Zenzic operates before the documentation build and does not depend on a particular generated-output format.

That gives us several practical properties:

Zenzic can run before the documentation generator;
CI can fail fast;
the core analysis does not need to execute the documentation stack;
multiple documentation engines can be supported through adapters;
findings can point directly to the author's source file.

This source-first approach is important to our architecture.

At the same time, it has a clear boundary.

A Markdown source scan cannot prove that an MDX component compiles, that a plugin behaves correctly, or that the final rendered HTML is accessible.

We therefore do not consider Zenzic a replacement for the final build and rendering tests.

We see it as a pre-build integrity gate.

The documentation build still needs to run.

The rendered site still needs to be tested.

Accessibility still needs to be checked.

Zenzic addresses a different layer of the problem.

Deterministic by design

Determinism is one of our most important engineering requirements.

Identical source input should produce the same findings, score, and gate result.

We built the execution model around three rules:

lint the source, not the generated output;
avoid subprocesses in the core analysis loop;
prefer pure-function-first validation and scoring.

These choices are intended to make the core analysis predictable and reproducible.

We also use a non-backtracking RE2-based engine for the relevant pattern matching, and the project is designed around a linear 
𝑂
(
𝑁
)
 analysis model.

“Linear” does not mean that every run will be instantaneous.

Startup time, filesystem access, repository size, adapter work, and output generation still matter.

The useful claim is narrower:

The core analysis is designed to scale predictably with the amount of documentation being examined.

We care about this because a CI quality gate should not become a source of unpredictable pipeline behaviour as a documentation repository grows.

One command to start

A standalone Markdown repository can run:

uvx zenzic check all docs/


For a project using a documentation framework:

uvx zenzic check all .


We support standalone repositories as well as framework-oriented workflows through adapters, including MkDocs, Zensical, and Docusaurus-oriented setups.

The intended gate semantics are straightforward:

exit 0 → no blocking findings
exit 1 → quality findings block the merge
exit 2 → security finding detected
exit 3 → path-traversal guard violation


The exact policy should always be verified against the installed version.

The principle, however, is important:

CI needs machine-readable outcomes, not merely a coloured report that developers must interpret manually.

That is why exit codes are part of the design rather than an afterthought.

Configuration without ambiguity

Zenzic uses a three-level configuration priority chain:

1. .zenzic.toml
2. [tool.zenzic] in pyproject.toml
3. built-in defaults


The repository root is found by walking upward from the current working directory until Zenzic encounters a .git directory, .zenzic.toml, or pyproject.toml.

The crucial rule is that .zenzic.toml wins unconditionally.

If it exists, Zenzic ignores the [tool.zenzic] table in pyproject.toml. The two files are not merged.

We chose this policy deliberately.

Field-by-field precedence rules can be difficult to reason about during incident response or CI debugging. We would rather have one explicit configuration source win than require users to reconstruct a merged configuration mentally.

A configuration might look like this:

docs_dir = "docs"
fail_under = 90

[build_context]
engine = "mkdocs"

[[custom_rules]]
id = "ZZ-NODRAFT"
pattern = "(?i)\\bDRAFT\\b"
message = "Remove DRAFT marker before publishing."
severity = "warning"


The same fields can be placed under [tool.zenzic] in pyproject.toml, with nested tables adjusted accordingly:

[tool.zenzic]
docs_dir = "docs"
fail_under = 90

[tool.zenzic.build_context]
engine = "mkdocs"

[[tool.zenzic.custom_rules]]
id = "ZZ-NODRAFT"
pattern = "(?i)\\bDRAFT\\b"
message = "Remove DRAFT marker before publishing."
severity = "warning"


There is one design choice we think users should understand: unknown fields are silently ignored.

This helps newer configuration files remain usable with older versions, but it can also hide typographical errors.

A misspelled setting may look accepted while having no effect.

Projects adopting Zenzic should therefore consider using strict configuration validation where available, or validating their configuration in CI until this behaviour is fully understood.

We prefer explicit configuration failures whenever a policy can materially affect a quality or security gate.

Configuration is part of the safety model

A broken configuration should not silently fall back to defaults.

Zenzic raises a configuration error and exits immediately when the winning TOML file contains a syntax error.

For a quality or security gate, we consider this safer behaviour.

Continuing with an unintended configuration can create a false sense of protection.

The broader principle is:

A security or quality control must fail visibly when its policy cannot be loaded.

We apply the same thinking to adapters, suppressions, and scoring.

An invisible fallback may be convenient during development, but it is dangerous in a production gate because the user may believe a policy is active when it is not.

Suppression debt is still debt

Every real repository contains exceptions.

Some links are intentionally external.

Some pages are historical.

Some words are valid in a migration record but forbidden in active documentation.

A practical tool must support suppressions.

But suppressions create their own risk: they can become permanent concealment.

We therefore treat suppression debt as a measurable property.

Zenzic provides suppression auditing and a configurable cap. For example:

CAP exceeded — exit 1

Active suppressions: 43
CAP limit: 30
Excess debt: +13


The goal is not to make exceptions impossible.

The goal is to make them visible.

An exception should have an owner, a reason, and ideally an expiry or review path.

The same principle applies to the documentation quality score.

Zenzic's deterministic score and component metrics can show movement in areas such as:

internal-link health;
anchor stability;
orphan detection;
unused assets;
navigation isolation.

But we do not want the score to become a vanity metric.

A score should guide investigation.

It should never replace reading the actual findings.

Can Zenzic replace existing tools?

Usually, no—not completely.

We did not build Zenzic to replace the entire documentation ecosystem.

Different tools solve different problems:

Tool	Primary responsibility	Relationship with Zenzic
markdownlint	Markdown style and formatting	Complementary
Vale	Editorial style and terminology	Complementary
Lychee	Link and HTTP endpoint checking	Partial overlap
Codespell	Spelling errors	Complementary
Gitleaks or TruffleHog	Secrets across repository content and history	Complementary, not automatically replaceable
MkDocs/Docusaurus/Zensical build	Rendering, plugins, and compilation	Not replaceable
Browser or HTML tests	Accessibility and rendered behaviour	Not replaceable

Zenzic can replace scripts that were custom-built to detect orphan pages, unused assets, missing local files, or certain navigation defects.

It may also consolidate parts of a link-checking and documentation-security pipeline.

But we do not want to position it as a universal replacement.

The final build still needs to run.

MDX components still need to compile.

Rendered HTML still needs testing.

Repository-wide secret scanning still has a broader scope.

Our intended position is:

Zenzic is the structural and security layer of a documentation toolchain, not the entire toolchain.

What Zenzic does not try to replace

We think this distinction is important enough to state explicitly.

We are not trying to replace your documentation builder.

We are not trying to replace Markdown style linters.

We are not trying to replace editorial style tools.

We are not trying to replace repository-wide secret scanners.

We are not trying to replace browser-based accessibility or rendering tests.

We are trying to enforce a different property:

Documentation integrity at source level.

That is the problem we designed Zenzic to solve.

Why adopt it?

We think Zenzic is useful when documentation has operational or security significance.

That includes:

API and SDK documentation;
deployment and infrastructure guides;
public open source repositories;
multi-team documentation portals;
multi-repository documentation systems;
documentation with generated navigation;
projects where broken references cause support incidents;
repositories where examples may contain sensitive configuration.

The strongest argument is not that Zenzic has more rules than a linter.

It is that it enforces a different contract:

Documentation must remain reachable, referentially valid, safe, and reviewable as the repository evolves.

This becomes particularly valuable when documentation changes frequently and manual review cannot inspect every relationship.

For larger repositories, the benefit is not simply finding more defects.

It is moving mechanical verification from human review into an automated, repeatable gate.

Why not adopt it?

We do not think everyone needs Zenzic.

If your repository contains a small README and a handful of Markdown files, you probably do not need a documentation-integrity engine.

A simple link checker may be enough.

You should also think carefully before adding Zenzic if:

the documentation has no meaningful graph or navigation;
a simpler tool already solves the actual problem;
the project cannot afford another evolving dependency;
the documentation uses highly dynamic MDX that the adapter cannot model;
the team is unwilling to triage false positives;
the pipeline already has several overlapping gates with no clear ownership.

A new quality tool creates its own maintenance burden.

Developers must learn finding codes, configure exclusions, manage suppressions, upgrade versions, and resolve disagreements with existing tools.

A tool that produces too much noise becomes a decorative CI badge.

We therefore think the adoption case should be based on measured defects found in a real repository, not on the length of the rule catalog.

A reasonable adoption plan

The safest approach is a staged rollout.

Phase one: observe

Run Zenzic locally and in CI without blocking merges.

Collect:

total findings;
confirmed defects;
false positives;
duplicate findings;
execution time;
adapter incompatibilities;
suppression candidates.

The first goal is to understand the repository, not to impose a new policy overnight.

Phase two: classify

Separate findings into:

security-critical;
hard structural errors;
warnings;
editorial suggestions;
intentional exceptions.

Do not begin by enabling every rule as a mandatory gate.

Phase three: block high-confidence failures

Start with findings such as:

missing local files;
missing anchors;
credential leaks;
path traversal;
missing configured assets.

These are easier to explain and generally have a clear remediation path.

Phase four: measure regression

Save a baseline or score and ensure that new changes do not make the documentation worse.

Existing technical debt should be handled deliberately rather than creating an impossible requirement to fix the entire repository in a single pull request.

The objective is to stop the debt from growing while giving the team a practical path to reduce it.

Phase five: remove duplication

Only after comparing results should you decide whether Zenzic makes custom scripts or overlapping checks unnecessary.

The goal is not to maximize the number of tools.

The goal is to maximize defect detection per unit of maintenance.

A minimal CI example

A project can begin with a simple command:

- name: Check documentation integrity
  run: uvx zenzic check all .


For a Python project, configuration can live in pyproject.toml:

[tool.zenzic]
docs_dir = "docs"
fail_under = 90


For a repository with a more explicit separation of concerns, use .zenzic.toml instead.

This makes the documentation policy visible as a dedicated artifact and ensures it takes precedence over embedded configuration.

The important part is not the number of lines in the workflow.

It is that the check runs before merge and produces a deterministic result that the repository can enforce.

Documentation integrity as a production property

The reason we built Zenzic is ultimately simple.

We do not think documentation should be treated as something that gets checked only when someone has time.

When documentation is part of a product, it has dependencies, references, topology, navigation, assets, and security boundaries.

Those properties can fail.

They can also be tested.

That is why we built Zenzic around three principles:

Reduce risk by detecting structural and security failures before release.
Save review time by automating mechanical checks that would otherwise create repetitive review loops.
Make CI reliable by tying the same repository state to the same findings and the same gate result.

We are not claiming that Zenzic replaces every other documentation tool.

We are not claiming that a source-level integrity scan can replace a full documentation build.

We are not claiming that every repository needs another quality gate.

Our claim is narrower—and, we think, more useful:

Documentation integrity should be a testable property of the repository.

For a tiny project, that may be unnecessary.

For an API, SDK, platform, or open source project with a growing documentation graph, it can be the missing quality gate between:

“The build passed.”

and

“The documentation is actually safe, reachable, and usable.”

That is the problem we built Zenzic to solve.

Project: https://zenzic.dev/

Documentation: https://zenzic.dev/

License: Apache-2.0

References

[1] Zenzic — Deterministic Document Integrity Engine - https://zenzic.dev/

[2] Zenzic — Why Zenzic? - https://zenzic.dev/explanation/why-zenzic/
