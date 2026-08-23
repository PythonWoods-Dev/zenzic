<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z303 — Duplicate Definition Gallery Example

This page defines the same reference ID twice,
demonstrating **Z303 DUPLICATE_DEF** detection.

## API Reference

See the [API documentation][api] for endpoint details.

The new [API][api] includes a breaking change in `/v2/auth`.

Duplicate reference definitions are risky because different Markdown
renderers resolve the ambiguity differently, so the same source file can
render distinct links depending on the toolchain. See the
[CommonMark specification](https://spec.commonmark.org/0.31.2/#link-reference-definitions)
for the formal first-wins resolution rule.

[api]: https://api-v1.example.com
[api]: https://api-v2.example.com
<!-- The `api` reference ID is defined twice above — once for v1, once for v2.
     That is the intentional defect that triggers Z303. -->
