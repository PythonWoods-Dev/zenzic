<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- markdownlint-disable MD052 -->

# Z301 — Dangling Reference Gallery Example

This page uses a reference-style link whose ID is never defined,
demonstrating **Z301 DANGLING_REF** detection.

## Content With Dangling Reference

To get started, [Click here][missing-ref] for the installation guide.

Note: `missing-ref` has no corresponding `[missing-ref]: url` definition
anywhere in this file — that is the intentional defect that triggers Z301.

## What Zenzic Reports

```text
docs/index.md:12:  Z301  DANGLING_REF  reference ID 'missing-ref' is used but never defined
```

Run `zenzic check references` to reproduce the finding.

Dangling references are easy to introduce during a rename: an author
updates the definition line but forgets one of the inline citations, and
the mismatch only surfaces when a linter checks reference integrity.
