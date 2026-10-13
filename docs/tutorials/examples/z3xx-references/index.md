---
title: Reference Integrity Scenarios (Z3xx)
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Reference Integrity Scenarios (Z3xx)

Interactive lab scenarios and test fixtures for reference link integrity rules (`Z3xx`). These fixtures demonstrate the three-pass reference pipeline detecting dangling reference shortcuts (`Z301`), dead link definitions (`Z302`), and duplicate reference key definitions (`Z303`).

Run `zenzic lab z302` to test the dead-definition scenario interactively (`z301` and `z303` cover the other two), or return to the [Lab Gallery Overview](../index.md).

The scenario carries its own fixture, so nothing has to be set up first:

```text
--8<-- "snippets/lab-z3xx.txt"
```
