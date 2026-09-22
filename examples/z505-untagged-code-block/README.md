<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z505 UNTAGGED_CODE_BLOCK — Gallery Example

**Category:** Z5xx Content Quality
**Expected exit:** 1 (warnings)

## What this demonstrates

`docs/index.md` contains a fenced code block with no language specifier:

````text
```
this code block has no language tag
```
````

Zenzic's built-in `UntaggedCodeBlockRule` (Z505) is always active. It flags
fenced blocks whose opening fence has no language identifier, which disables
syntax highlighting and language-specific quality checks.

## Run it

```bash
zenzic lab z505
# or directly:
zenzic check references
```

## Expected output

```text
docs/index.md:9:  Z505  UNTAGGED_CODE_BLOCK  fenced code block has no language specifier
```

Exit code **1**.

## Fix

Add a language identifier to the opening fence:

````text
```bash
this code block has no language tag
```
````

Use `text` or `plain` for literal content with no specific language.
