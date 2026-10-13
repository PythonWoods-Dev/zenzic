<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z503 SNIPPET_ERROR — Gallery Example

**Category:** Z5xx Content Quality
**Expected exit:** 1 (errors)

## What this demonstrates

`docs/index.md` contains a fenced Python code block with a `SyntaxError`:

````python
def compute_total(
    items =   # SyntaxError: incomplete expression
````

Zenzic's built-in snippet validator parses `python` fenced blocks using the
`ast` module. If the block fails to parse, it is flagged as Z503 SNIPPET_ERROR —
a code sample that cannot be executed as documented.

## Run it

```bash
zenzic lab z503
# or directly:
zenzic check snippets
```

## Expected output

```text
docs/index.md:10:  Z503  SNIPPET_ERROR  Python block has a syntax error: invalid syntax (<unknown>, line 2)
```

Exit code **1**.

## Fix

Fix the Python syntax error in the code block. If the snippet is intentionally
partial (showing a fragment), add a language tag other than `python`
(e.g. ` ```text `) to skip validation.
