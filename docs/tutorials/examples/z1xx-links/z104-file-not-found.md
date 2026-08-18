---
description: "Walk through the z104-file-not-found fixture: a link pointing to api/reference.md which does not exist on disk, triggering Z104 FILE_NOT_FOUND at exit code 1."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z104 — File Not Found

**Z-Code:** `Z104 FILE_NOT_FOUND` · **Engine:** `standalone` · **Exit:** `1`

<Z104FileNotFound />

## The Fixture

The fixture lives at `examples/z104-file-not-found/` in the Zenzic repository.
The source document is `docs/index.md`, which contains a link to `api/reference.md`
— a file that does not exist on disk:

| Line | Link | Target | Exists? |
| :--: | :--- | :----- | :-----: |
| 11   | `[API Reference](api/reference.md)` | `docs/api/reference.md` | ✘ |

```toml title="examples/z104-file-not-found/.zenzic.toml"
docs_dir = "docs"
fail_under = 0

[build_context]
engine = "standalone"
```

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z104-file-not-found
uvx zenzic check all
```

Expected output:

```text
standalone · 1 file (1 docs, 0 assets) · 0.0s · 67 files/s

docs/index.md:11:44  x  [Z104]  'api/reference.md' not found in docs

     9  │  ## API Reference
    10  │
    11  ❱  For the complete API specification, see the [API Reference](api/refer…
    12  │  The API reference contains all endpoints, request formats, and respo…
    13  │

────────────────────────────────────────────────────────────────────────────────

Summary:  x 1 error  ! 0 warnings  i 0 info  · 1 file with findings

FAILED: Hard errors detected. Exit code 1 is mandatory.
```

Exit code: `1`

## Interpreting the Output

The `Z104` finding indicates a **FILE_NOT_FOUND** issue.

This error is raised when a relative link in a Markdown page points to a file
path that does not exist in the `docs_dir` tree. Unlike `Z101 LINK_BROKEN` (which
covers structural routing issues), Z104 is the precise signal for a missing
filesystem entry:

- **Scan Type:** `Link Validator`
- **Severity:** `Error`
- **Impact:** Missing link targets break navigation and deduct **8.0 DQS points**
  — the highest penalty in the Z1xx group.

## Resolve the Issue

1. Create the missing file at `docs/api/reference.md`.
2. Or correct the link target in `docs/index.md` to point to an existing file.

```diff
- For the complete API specification, see the [API Reference](api/reference.md).
+ For the complete API specification, see the [API Reference](api/index.md).
```

## Footnotes Parsing Behavior

Footnote definitions (such as `[^1]: footnote text`) are parsed and recognized correctly by Zenzic's link parser. Zenzic automatically ignores footnotes during the link verification process, preventing them from being mistakenly validated as filesystem links, thereby avoiding false-positive `Z104` errors.

## See Also

- [Z101 — Broken Links](z101-broken-links) — routing-level link integrity.
- [Z102 — Anchor Missing](z102-anchor-missing) — fragment-level link integrity
  (file exists, heading anchor absent).
- [Checks Reference — Z104](../../../reference/checks) — full rule specification.
