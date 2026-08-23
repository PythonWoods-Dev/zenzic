<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z101 LINK_BROKEN (missing file) — Gallery Example

**Category:** Z1xx Link Integrity
**Expected exit:** 1 (error)

## What this demonstrates

`docs/index.md` contains a link to `api/reference.md`, which does not exist on
disk. Zenzic's link validator reports all unreachable links — including
missing internal files — under the consolidated `Z101 LINK_BROKEN` code.
`Z104 FILE_NOT_FOUND` is defined in the finding-codes catalog but is not
emitted by the current engine; missing-file links surface as `Z101` (see
`zenzic/core/rules.py`, `VSMBrokenLinkRule`).

## Run it

```bash
cd examples/z104-file-not-found
uvx zenzic check all
```

## Expected output

```text
docs/index.md:10:44  x  [Z101]  'api/reference.md' not found in docs
```
