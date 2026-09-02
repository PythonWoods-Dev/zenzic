---
description: "Walk through the z103-orphan-link fixture: a link to an existing file that is absent from site navigation, triggering Z103 ORPHAN_LINK."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z103 — Orphan Link

**Z-Code:** `Z103 ORPHAN_LINK` · **Engine:** `zensical` · **Exit:** `1`

<Z103OrphanLink />

---

## The Fixture

The fixture lives at `examples/z103-orphan-link/` in the Zenzic repository.
It contains two documents and two configuration files:

| File | Role |
| :--- | :--- |
| `docs/index.md` | Source — in nav, links to `guide.md` at line 16 |
| `docs/guide.md` | Target — exists on disk, **not** in nav |
| `.zenzic.toml` | Engine config (`zensical`), `fail_under = 0` |
| `zensical.toml` | Nav declaration — `guide.md` deliberately excluded |

`zensical.toml` declares a nav with only `index.md`. The file `guide.md` exists on
disk but has no nav entry — its status in the Virtual Site Map (VSM) is
`ORPHAN_BUT_EXISTING`. When `index.md` links to it at line 16, Zenzic's
`VSMBrokenLinkRule` fires Z103: the link bypasses navigation and makes the page
reachable only via direct URL.

```toml title="examples/z103-orphan-link/zensical.toml"
[project]
site_name = "Z103 Example"
docs_dir  = "docs"
nav = [
    "index.md",
]
```

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z103-orphan-link
uvx zenzic check links
```

Expected output:

```text
zensical - 2 files (2 docs, 0 assets) - 0.0s - 101 files/s

docs/guide.md  !  [Z402]  Physical file not listed in navigation.

docs/index.md:16:2  x  [Z101]  'guide.md' resolves to '/guide/' which exists on
disk but is not listed in the site navigation (UNREACHABLE_LINK) — add it to nav
in mkdocs.yml or remove the link

    14  │  The following link points to a page that exists on disk but has no
nav entry:
    15  │
    16  ❱  - [Guide](guide.md) — `guide.md` exists on disk, but it is **not in
the nav** → **Z103**
        │    ^^^^^^^^^^^^^^^^^
    17  │
    18  │  ## What Zenzic Reports

────────────────────────────────────────────────────────────────────────────────

Summary:  x 1 error  ! 1 warning  i 0 info  - 2 files with findings

FAILED: Hard errors detected. Exit code 1 is mandatory.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `1`

VSM context (documentation note, not CLI output):

- Target file state: `ORPHAN_BUT_EXISTING`
- The file exists on disk but is absent from `zensical.toml` navigation.

---

## Interpreting the Output

The `Z103` finding indicates a **ORPHAN_LINK** issue.

This error or warning is raised by Zenzic when a markdown page exists and is linked to, but the link target is not reachable via the site navigation structure (e.g., it is omitted from the sidebar config/nav contract). In this specific example:

- **Scan Type:** `Link Validator`
- **Severity:** `Error`
- **Impact:** Orphaned links can lead to isolated content pockets and result in a DQS deduction of 2.0 points.

---

## Resolve the Issue

Exit code 1 is triggered. To fix this, register the target page in the `nav` section of the engine configuration file to integrate it into the site navigation hierarchy.

---

## See Also

- [z101 — Broken Links](z101-broken-links) — the target file does not exist on disk.
- [z102 — Anchor Missing](z102-anchor-missing) — the target file exists but the heading anchor does not.
- [z402 — Orphan Page](../../examples/z4xx-topology/z402-orphan-page) — the inverse: a page that is not in the nav and has no link pointing to it at all.
- [Checks Reference](../../../reference/checks) — full rule specification.
