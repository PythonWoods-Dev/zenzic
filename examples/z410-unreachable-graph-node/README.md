<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z410 UNREACHABLE_GRAPH_NODE — Gallery Example

**Category:** Z4xx Structural
**Expected exit:** 1 (warnings)
**Engine required:** zensical

## What this demonstrates

`docs/secret.md` exists on disk but has no incoming links and is not in the navigation manifest. Therefore it is an unreachable graph node.

## Run it

```bash
zenzic check .
```

## Expected output

```text
docs/secret.md:1:  Z410  UNREACHABLE_GRAPH_NODE  Document is isolated and unreachable from the navigation entry points: '/secret.md'
```

Exit code **1**.

## Fix

Either add `"secret.md"` to the `nav` array in `zensical.toml`, link to it from `index.md`, or suppress it using `<!-- zenzic:ignore:Z410 -->`.
