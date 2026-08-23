<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- markdownlint-disable MD040 -->

# Z505 — Untagged Code Block Gallery Example

This page demonstrates **Z505 UNTAGGED_CODE_BLOCK** detection.

## Usage Example

Run the following command to get started:

```
zenzic check all --fail-under 0
```

The fenced code block above has no language specifier — the opening fence is
just ` ``` ` without a language tag like `bash` or `text` → **Z505**.

## What Zenzic Reports

```text
docs/index.md:13:  Z505  UNTAGGED_CODE_BLOCK  fenced code block has no language specifier
```

Run `zenzic check content` to reproduce the finding.

Language tags on fenced code blocks do more than enable syntax
highlighting — many static site generators also use them to select the
correct linter or validator for that snippet during a build.
