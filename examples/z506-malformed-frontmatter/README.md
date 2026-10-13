<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z506 MALFORMED_FRONTMATTER — Gallery Example

**Category:** Z5xx Content Quality
**Expected exit:** 1 (errors)

## What this demonstrates

`docs/index.md` opens with `--` instead of `---`. The block looks like
frontmatter to a person and is not frontmatter to a parser, so every key it
declares is silently absent.

That silence is why this is an error rather than a warning. A rule requiring a
frontmatter key does not report "the key is wrong" — it reports the key as
missing, pointing at a file whose author can see it written two lines below the
heading. `Z506` names the real cause.

## Run it

```bash
zenzic lab z506
```
