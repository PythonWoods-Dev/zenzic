<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z502 SHORT_CONTENT — Gallery Example

**Category:** Z5xx Content Quality
**Expected exit:** 1 (warnings)

## What this demonstrates

`docs/index.md` has only 8 words of prose, which is below the default threshold
of 50 words (`placeholder_max_words = 50`). Zenzic flags sparse pages as Z502
SHORT_CONTENT — they are likely stubs that were published before being finished.

The file deliberately avoids placeholder patterns like `TODO:` so that only Z502
fires (not Z501).

## Run it

```bash
zenzic lab z502
# or directly:
zenzic check placeholders
```

## Expected output

```text
docs/index.md:1:  Z502  SHORT_CONTENT  page has 8 words (minimum: 50)
```

Exit code **1**.

## Fix

Write the full page content, or raise the threshold in `.zenzic.toml`:

```toml
[content]
placeholder_max_words = 10
```
