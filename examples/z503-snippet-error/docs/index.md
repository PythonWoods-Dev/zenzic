<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z503 — Snippet Error Gallery Example

This page contains a Python code block with a syntax error,
demonstrating **Z503 SNIPPET_ERROR** detection.

## Compute Total

Use the `compute_total` function to sum a list of prices:

```python
def compute_total(
    items =   # SyntaxError: incomplete expression
```

The code block above is syntactically invalid — `items =` is an incomplete
expression. Zenzic's `ast`-based validator catches this → **Z503**.

## What Zenzic Reports

```text
docs/index.md:13:  Z503  SNIPPET_ERROR  Python block has a syntax error: invalid syntax (<unknown>, line 2)
```

Run `zenzic check content` to reproduce the finding.

Validating embedded code samples against a real parser catches copy-paste
errors that a plain-text spell checker would never notice, keeping
tutorials trustworthy for readers who copy the snippet verbatim.
