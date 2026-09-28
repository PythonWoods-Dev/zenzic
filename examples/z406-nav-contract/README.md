<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z406 NAV_CONTRACT — Gallery Example

**Category:** Z4xx Topology & Assets
**Expected exit:** 1 (error)

## What this demonstrates

`mkdocs.yml` declares `extra.alternate` with `link: /it/` but no Italian
documentation pages exist — `/it/` is not in the Virtual Site Map.
Zenzic fires Z406 NAV_CONTRACT — a hard error mandating exit 1.

## Run it

```bash
cd examples/z406-nav-contract
uvx zenzic check all
```

## Expected output

```text
docs/(nav)  x  [Z406]  mkdocs.yml extra.alternate[it]: link '/it/' does not
correspond to any URL the build engine will generate. The Virtual Site Map
contains no entry for '/it/'.
```

## It also declares its Markdown extensions

This is the one gallery fixture whose `mkdocs.yml` carries a
`markdown_extensions` key, and it is there to exercise the adapter-extension
contract rather than to demonstrate `Z406`.

It enables `admonition` and not `pymdownx.details`. So in *this* project `!!!`
opens a container and `???` does not — which makes the four-space-indented
lines under the `??? note` block a CommonMark §4.4 code block, not container
content. The heading inside it ends with a period and is never reported as
`Z517 HEADING_PUNCTUATION`, because it is never read as a heading.

Under the default vocabulary the same file reports that finding. That
difference is asserted in `tests/test_container_vocabulary_contract.py`.
