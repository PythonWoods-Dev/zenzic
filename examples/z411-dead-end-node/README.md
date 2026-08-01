<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z411 DEAD_END_NODE — Gallery Example

**Category:** Z4xx Structural
**Expected exit:** 1 (warnings)
**Engine required:** any

## What this demonstrates

`docs/deadend.md` exists and is linked from `index.md`, but it has no outgoing links.
Therefore, it forms a structural dead end in the documentation graph. Visitors reaching this page will have nowhere to go.

## Run it

```bash
zenzic check .
```

## Expected output

```text
docs/deadend.md:1:  Z411  DEAD_END_NODE  Document has no outgoing links and forms a structural dead end: '/deadend.md'
```

Exit code **1**.

## Fix

Add an outgoing link to another page in `deadend.md`, or suppress the warning with `<!-- zenzic:ignore:Z411 -->`.
