<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Asset Integrity — Z405 Gallery Example

This document is intentionally clean. The `assets/banner.png` image exists
in the project but is never referenced here — which triggers **Z405
UNREFERENCED_ASSET**.

## About this project

A minimal standalone documentation project demonstrating Zenzic's asset
integrity check. All link references in this document are valid.

## Run it

```bash
zenzic lab z405
# or directly:
zenzic check assets
```

Unreferenced assets accumulate over time as pages are rewritten and old
screenshots or diagrams are swapped out without anyone deleting the files
they replaced, quietly bloating the published site.
