<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z302 — Dead Definition Gallery Example

This page defines a reference ID that is never used,
demonstrating **Z302 DEAD_DEF** detection.

## Content

Welcome to the documentation. Follow the instructions in the
[Quick Start](https://example.com/quickstart) guide to get up and running.

For more details, see the [API reference](https://example.com/api).

Reference-style definitions that are declared but never used are a common
form of documentation debt: they linger in the source, drift out of date,
and mislead future editors into thinking they are load-bearing. See the
[CommonMark specification](https://spec.commonmark.org/0.31.2/#link-reference-definitions)
for the formal reference-definition syntax.

[setup]: https://example.com/setup

<!-- The "setup" reference definition above is never used by any link in this
     file — that is the intentional defect for Z302. -->
