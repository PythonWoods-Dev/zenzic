<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z106 CIRCULAR_LINK — Gallery Example

**Category:** Z1xx Link Integrity
**Expected exit:** 0 (informational)

## What this demonstrates

`docs/index.md` links to `docs/setup.md`, and `docs/setup.md` links back. Both
targets resolve, so this is not a broken link — every hop is valid. What `Z106`
reports is the shape of the graph rather than the health of any one edge: a
chain a reader can follow indefinitely without reaching new material.

It is a `note`, not an error, and carries no score penalty. A loop between two
pages is often deliberate — reciprocal navigation between a guide and its
reference is exactly this shape — so the code exists to make the structure
visible, not to condemn it.

## Run it

```bash
zenzic lab z106
```
