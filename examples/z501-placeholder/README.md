<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z501 PLACEHOLDER — Gallery Example

**Category:** Z5xx Content Quality
**Expected exit:** 1 (warnings)

## What this demonstrates

`docs/index.md` contains two lines matching the built-in placeholder patterns:
`TODO: content goes here` and `Coming soon!`.

These strings signal stub content that was never completed before publication.
Zenzic's content scanner detects them in Pass 1 (Placeholder Sweep) and reports
each as Z501 PLACEHOLDER.

## Run it

```bash
zenzic lab z501
# or directly:
zenzic check placeholders
```

## Expected output

```text
docs/index.md:7:   Z501  PLACEHOLDER  placeholder pattern 'TODO:' matched
docs/index.md:11:  Z501  PLACEHOLDER  placeholder pattern 'Coming soon!' matched
```

Exit code **1**.

## Fix

Replace placeholder text with real content, or remove the sections entirely.
To suppress a pattern for a legitimate occurrence, add it to
`[content].ignored_placeholder_patterns` in `.zenzic.toml`.
