---
description: "Walk through the z101-broken-links fixture: two internal link targets that do not exist on disk, triggering Z101 LINK_BROKEN at exit code 1."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z101 — Broken Links

**Z-Code:** `Z101 LINK_BROKEN` · **Engine:** `standalone` · **Exit:** `1`

<Z101BrokenLinks />

## The Fixture

The fixture lives at `examples/z101-broken-links/` in the Zenzic repository.
The source document is `docs/index.md`, which contains two links pointing to files
that do not exist on disk:

| Line | Link | Target | Exists? |
| :--: | :--- | :----- | :-----: |
| 7    | `[Getting Started](missing.md)` | `missing.md` | ✘ |
| 8    | `[Setup Guide](guide/setup.md)` | `guide/setup.md` | ✘ |

Neither `missing.md` nor the `guide/` subdirectory exists in the fixture.
Both links are therefore broken. Zenzic fires Z101 for each one.

```toml title="examples/z101-broken-links/.zenzic.toml"
docs_dir = "docs"
fail_under = 0

[build_context]
engine = "standalone"
```

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z101-broken-links
uvx zenzic check links
```

Expected output:

```text
standalone - 1 file (1 docs, 0 assets) - 0.0s - 65 files/s

docs/index.md:11:2  x  [Z104]  'missing.md' not found in docs

     9  │  ## Broken References
    10  │
    11  ❱  - [Getting Started](missing.md) — this file does not exist → **Z101**
        │    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    12  │  - [Setup Guide](guide/setup.md) — this directory does not exist →
**Z101**
    13  │

docs/index.md:12:2  x  [Z104]  'guide/setup.md' not found in docs

    10  │
    11  │  - [Getting Started](missing.md) — this file does not exist → **Z101**
    12  ❱  - [Setup Guide](guide/setup.md) — this directory does not exist →
**Z101**
        │    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    13  │
    14  │  ## What Zenzic Reports

────────────────────────────────────────────────────────────────────────────────

Summary:  x 2 errors  ! 0 warnings  i 0 info  - 1 file with findings

FAILED: Hard errors detected. Exit code 1 is mandatory.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `1`

## Interpreting the Output

The `Z101` finding indicates a **LINK_BROKEN** issue.

This error or warning is raised by Zenzic when a reference link points to an invalid path. The link is broken because the target file does not map to any valid route in the Virtual Site Map. In this specific example:

- **Scan Type:** `Link Validator`
- **Severity:** `Error`
- **Impact:** Broken links severely degrade the user experience and reduce the Documentation Quality Score (DQS) by deducting a penalty of 8.0 points.

## Resolve the Issue

Exit code 1 is triggered in CI pipeline gates when broken links are detected to prevent deployment of dead references. Remediation requires creating the missing destination file or correcting the target path inside the markdown source file.

## See Also

- [z102 — Anchor Missing](z102-anchor-missing) — the fragment-level variant of link integrity:
  the target file exists, but the heading anchor does not.
- [z103 — Orphan Link](z103-orphan-link) — link targets that exist on disk but are absent from
  the site navigation (zensical engine required).
- [Checks Reference — Z101](../../../reference/checks) — full rule specification.
