<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z501 — Placeholder Content Gallery Example

This page demonstrates **Z501 PLACEHOLDER** detection.

## Installation

TODO: content goes here

## Advanced Usage

TODO: Add advanced usage examples once the feature is complete.

Coming soon!

## What Zenzic Reports

```text
docs/index.md:10:  Z501  PLACEHOLDER  placeholder pattern 'TODO:' matched
docs/index.md:16:  Z501  PLACEHOLDER  placeholder pattern 'Coming soon!' matched
```

Run `zenzic check content` to reproduce the findings.

Placeholder text is easy to forget once a page ships, since it renders
without any visual warning and only a targeted content scan will surface
it before a reader stumbles across an unfinished section.
