<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z101 LINK_BROKEN (external) — Gallery Example

**Category:** Z1xx Link Integrity
**Expected exit:** 1 (errors)

## What this demonstrates

`docs/index.md` contains a link to an external URL that cannot be reached or returns an HTTP error:
`[Broken Link](https://this-domain-does-not-exist-at-all-xyz.com)`.

Zenzic's link validator reports all unreachable links — internal or external —
under the consolidated `Z101 LINK_BROKEN` code. `Z109 EXTERNAL_LINK_BROKEN` is
defined in the finding-codes catalog but is not emitted by the current engine;
external link failures surface as `Z101` (see `zenzic/core/validator.py`,
`_check_external_links`).

## Run it

```bash
zenzic check links
```

## Expected output

```text
docs/index.md:7:  Z101  LINK_BROKEN  external link 'https://this-domain-does-not-exist-at-all-xyz.com' is broken
```

Exit code **1**.

## Fix

Correct the external URL or remove the broken link.
