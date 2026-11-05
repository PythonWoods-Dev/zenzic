<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z120 UNKNOWN_HTML_ATTRIBUTE — Gallery Example

**Category:** Z12x HTML Integrity
**Expected exit:** 0 (warnings — DQS penalised)

## What this demonstrates

`docs/index.md` contains `<a>` tags with valid HTML5 attributes
(`hreflang`, `ping`, `referrerpolicy`) that are **not in the Safe-Core list**.
The PolyglotExtractor emits **Z120** (warning) for each unknown attribute.

## Run it

```bash
zenzic lab z120
# or directly:
cd examples/z120-unknown-html-attr && zenzic check all
```

## How to suppress (if intentional)

```html
<a href="./page.md" hreflang="en" data-zenzic-ignore>link</a>
```

Each suppression costs **-1.0 pts** in the DQS.
