<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z205 FORBIDDEN_SCHEME — Gallery Example

**Category:** Z2xx Security
**Expected exit:** 2 (SECURITY BREACH — non-suppressible)

`docs/index.md` contains `javascript:` and `data:` URIs.
**Z205 is NEVER suppressible** — `data-zenzic-ignore` has NO effect.

## Run it

```bash
zenzic lab z205
# or directly:
cd examples/z205-forbidden-scheme && zenzic check all
```

## Security Invariant

```html
<!-- This WILL still emit Z205 — data-zenzic-ignore is ignored for Z205 -->
<a href="javascript:void(0)" data-zenzic-ignore>Cannot suppress</a>
```

This behaviour is by design. Z205 is a mandatory security gate (ADR-075).
