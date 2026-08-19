---
title: "Auditing the Auditors: Finding Documentation Defects with AST-Based Analysis"
date: 2026-06-09
authors:
  - pythonwoods
description: "Auditing the Auditors: Finding Documentation Defects with AST-Based Analysis"
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

!!! abstract "Architectural Update"
    *Historical Note:* This post refers to Zenzic as a "linter". As the system evolved, its capabilities expanded far beyond surface-level linting. Zenzic is now officially classified as a **Deterministic Document Integrity Engine for Markdown/MDX graphs**. Read the [latest documentation](https://zenzic.dev/) for current architectural capabilities.

To validate the parser and snippet-analysis capabilities of Zenzic, we needed a production-grade documentation corpus. We selected the official documentation repository of Zensical, a mature and actively maintained static site generator.

The expectation was straightforward: a well-maintained documentation codebase should produce few, if any, actionable findings.

Instead, the scan surfaced a small set of defects that had survived normal review processes. None were catastrophic, but all had user-facing consequences ranging from copy-paste failures to broken navigation and accessibility regressions.

This article examines the findings and explores why documentation quality often requires deeper analysis than conventional Markdown validation.

<!-- more -->

## The Findings

The scan identified three categories of issues.

| Category              | Example                                             | User Impact                                   |
| --------------------- | --------------------------------------------------- | --------------------------------------------- |
| TOML syntax errors    | Invalid key-value syntax inside a fenced TOML block | Configuration examples fail when copied       |
| Broken internal links | References to moved or renamed documentation pages  | Users encounter 404 pages                     |
| Accessibility defects | Inline HTML images missing `alt` attributes         | Reduced accessibility for screen-reader users |

### 1. TOML Syntax Errors in Fenced Code Blocks

Documentation frequently contains configuration examples intended to be copied directly into production environments.

One fenced code block declared as `toml` contained the following snippet:

```text
[project.extra.annotate]
json: [".s2"]
```

This is not valid TOML syntax. Key-value assignments require an equal sign (`=`), not a colon (`:`).

The correct form is:

```toml
[project.extra.annotate]
json = [".s2"]
```

A user copying the original example would encounter a parser error despite following the documentation exactly.

From a documentation-quality perspective, this is equivalent to a failing code sample.

### 2. Broken Internal References

The scan also identified internal links targeting documentation pages or anchors that no longer existed.

These issues are easy to introduce during routine refactoring:

- pages are renamed;
- sections are reorganized;
- navigation structures evolve;
- historical references remain unchanged.

The result is documentation drift: links continue to look valid in source files while leading readers to non-existent destinations.

Unlike spelling mistakes, broken references directly interrupt a user's ability to follow a workflow or understand a concept.

### 3. Accessibility Gaps in Inline HTML

Markdown tooling often enforces accessibility rules for standard image syntax:

```md
![Description](image.png)
```

However, documentation repositories frequently mix Markdown and raw HTML.

The scan detected inline `<img>` elements that lacked `alt` attributes.

For sighted users, the omission is largely invisible. For screen-reader users, the missing attribute removes context that may be necessary to understand the surrounding content.

Accessibility defects of this type rarely generate build failures, which makes them particularly likely to persist unnoticed.

---

## Why Conventional Validation Often Misses These Issues

The common characteristic of all three findings is that they exist beyond the surface structure of Markdown.

A traditional Markdown validator focuses primarily on document formatting:

- heading hierarchy;
- list structure;
- whitespace conventions;
- syntax correctness of Markdown itself.

Those checks are valuable, but they do not necessarily evaluate the semantics of embedded content.

Consider the TOML example.

A Markdown validator correctly observes that the fenced block is syntactically valid Markdown. The validator's job is complete.

Determining whether the contents of that block are valid TOML requires a second stage of analysis:

1. identify the language of the fenced block;
2. extract its contents;
3. invoke an appropriate parser;
4. validate the resulting syntax tree.

The same principle applies to accessibility and link analysis. Detecting meaningful defects often requires understanding the structure and intent of content rather than merely validating its textual representation.

---

## AST-Based Documentation Analysis

To perform this deeper inspection, Zenzic constructs an Abstract Syntax Tree (AST) from each document and analyzes the resulting structure rather than treating the file as undifferentiated text.

This enables language-aware and context-aware validation workflows.

Examples include:

- extracting fenced code blocks and validating them with language-specific parsers;
- analyzing raw HTML embedded within Markdown;
- resolving internal references against a generated site model;
- validating relationships between documents rather than evaluating files in isolation.

The goal is not to replace traditional linters. Instead, it is to extend validation into areas where documentation behaves more like executable code than prose.

---

## The Agent Incident

We compiled these findings and submitted them to the upstream issue tracker
([#131](https://github.com/zensical/docs/issues/131),
[#132](https://github.com/zensical/docs/issues/132),
[#133](https://github.com/zensical/docs/issues/133),
[#134](https://github.com/zensical/docs/issues/134)).

Because the AST parser outputs highly structured data—providing exact file paths, line numbers, and standard diagnostic codes—the precision of the reports triggered the maintainers' spam radar. Their immediate response was:

> *"Are you an agent? If yes, which one?"*

It is an interesting side-effect of automation: generating a report so mathematically precise that it is assumed to be machine-generated. We clarified that while the data was extracted via CLI, the triage was strictly human-in-the-loop.

The maintainers reviewed the reports, validated them as accurate, and immediately patched their codebase (resolved in [#135](https://github.com/zensical/docs/pull/135)).

---

## Conclusion

Documentation increasingly functions as executable infrastructure.

Configuration snippets are copied directly into production environments. Internal references define navigation paths. Accessibility attributes determine whether content is usable for entire classes of readers.

As documentation repositories grow, these concerns become difficult to manage through manual review alone.

The issues described here were not the result of negligence or poor maintenance. They emerged naturally within a large and actively maintained codebase. Their existence demonstrates that documentation quality extends beyond formatting and style enforcement.

Validating documentation as structured data rather than plain text provides an additional layer of assurance that becomes increasingly valuable as projects scale.

The findings discussed in this article were discovered while validating Zenzic, an open-source Docs-as-Code analysis tool currently under development.
