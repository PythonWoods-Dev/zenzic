---
title: "Zenzic v0.17.0: HTML Validation in Markdown Documents"
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
date: 2026-06-28
authors:
  - pythonwoods
categories:
  - Releases
  - Engineering
---
With the release of Zenzic v0.17.0, Zenzic expands its validation capabilities beyond Markdown syntax. In addition to Markdown links and assets, Zenzic can now analyze raw HTML references embedded in Markdown documents.

A common limitation of Markdown-focused tooling is that raw HTML embedded inside Markdown documents is not analyzed with the same rigor as native Markdown constructs. When developers embed anchor or image elements directly into their Markdown for custom layouts, broken links and missing assets can remain undetected.

With v0.17.0, HTML links and images are analyzed by the same validation pipeline used for Markdown references.

<!-- more -->

---

## The Uniform Resolver Pipeline (URP)

To support HTML validation while preserving the existing architecture, we introduced the **Uniform Resolver Pipeline (URP)**.

The Polyglot Extractor natively parses `<a>` and `<img>` tags directly within the Markdown document. Rather than relying on a DOM parser, HTML extraction is implemented as a DFA (Deterministic Finite Automaton) built on top of the Google RE2 engine.

This means that whether a link is written in standard Markdown format `[text](url)` or as raw HTML `<a href="url">text</a>`, it now passes through the same validation pipeline. Both are subjected to the same validation checks for orphaned references, broken paths, and missing assets.

This unified approach introduces five new diagnostic codes for HTML validation:

* **Z120 UNKNOWN_HTML_ATTRIBUTE**: Warns when an attribute is outside the supported Safe-Core list.
* **Z121 MISSING_OR_EMPTY_HREF**: Reports links with a missing or empty `href` attribute.
* **Z122 JUMP_LINK_DETECTED**: Warns about placeholder anchors such as `href="#"`.
* **Z123 NON_HTTP_SCHEME**: Flags non-resolvable URI schemes such as `mailto:` and `tel:`.
* **Z124 OPAQUE_HTML_CONTEXT**: Detects event handlers and routing-related attributes that cannot be analyzed reliably by Zenzic.

---

## Security: Z205 Forbidden Scheme

Raw HTML can introduce URI schemes that are unsafe or inappropriate in technical documentation. A malicious actor could attempt to embed executable payloads through schemes such as `javascript:` or `data:`.

To reduce the risk of unsafe links being introduced into documentation, v0.17.0 introduces the **Z205 FORBIDDEN_SCHEME** security rule.

This is not a warning. It is a critical, **non-suppressible** violation. If Zenzic detects a forbidden scheme, it immediately halts the pipeline with an Exit 2 status. Inline suppressions such as `data-zenzic-ignore` cannot bypass this rule. In environments using SARIF for CI/CD integrations, this triggers a `toolExecutionNotifications` alert, ensuring that the build fails before the documentation can be deployed.

---

## The Path Forward

The v0.17.0 release extends Zenzic's validation coverage to raw HTML embedded in Markdown documents. As we move towards v0.18.0, our focus will shift from CI/CD execution into the editor through the upcoming Zenzic Language Server (ZLS).

Check out the [Changelog](https://github.com/PythonWoods/zenzic/blob/main/CHANGELOG.md) for the full list of updates and bug fixes in this release.

Happy writing.
