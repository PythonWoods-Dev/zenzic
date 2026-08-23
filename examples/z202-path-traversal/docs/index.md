<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z202 — Path Traversal Gallery Example

This page intentionally escapes the `docs/` boundary,
demonstrating **Z202 PATH_TRAVERSAL** detection.

## Traversal Link

- [Config](../../private/secret.txt) — this link escapes `docs/` via `../..` → **Z202**

## What Zenzic Reports

```text
docs/index.md:11:  Z202  PATH_TRAVERSAL  '../../private/secret.txt' escapes the docs/ root boundary
```

Z202 is non-suppressible. Exit code 2.

Run `zenzic check links` to reproduce the finding.

For background on why documentation tooling enforces a strict root boundary,
see the [OWASP path traversal reference](https://owasp.org/www-community/attacks/Path_Traversal).
