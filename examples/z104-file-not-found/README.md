<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z104 FILE_NOT_FOUND (missing asset) — Gallery Example

**Category:** Z1xx Link Integrity
**Expected exit:** 1 (error)

## What this demonstrates

`docs/index.md` links to `assets/architecture.png`, which is not on disk.
Zenzic reports it as `Z104 FILE_NOT_FOUND`.

`Z104` and `Z101 LINK_BROKEN` divide the same question by target kind: a link to
a missing **asset** is `Z104`, a link to a missing **page** is `Z101`. This
example is the asset half.

## Run it

```bash
cd examples/z104-file-not-found
uvx zenzic check all
```

## Expected output

```text
docs/index.md:10:44  x  [Z101]  'api/reference.md' not found in docs
```
