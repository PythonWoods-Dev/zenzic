---
description: "Walk through the z107-circular-anchor fixture: a self-referential anchor link triggering Z107 CIRCULAR_ANCHOR at exit code 0."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z107 — Circular Anchor

**Z-Code:** `Z107 CIRCULAR_ANCHOR` · **Engine:** `standalone` · **Exit:** `0`

<Z107CircularAnchor />

---

## The Fixture

The fixture lives at `examples/z107-circular-anchor/` in the Zenzic repository.
The source document is `docs/guide.md`, which contains the link `[Setup](#setup)`
inside the `## Setup` heading section.

The link text **"Setup"** slugifies to `#setup`, the same fragment as the
containing `## Setup` heading — making it circular (clicking it scrolls to the
same place the user is already reading):

| Line | Link | Fragment | Self-referential? |
| :--: | :--- | :------- | :---------------: |
| 14   | `[Setup](#setup)` | `#setup` (== parent heading) | ✓ |

```toml title="examples/z107-circular-anchor/.zenzic.toml"
docs_dir = "docs"
fail_under = 0

[build_context]
engine = "standalone"
```

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z107-circular-anchor
uvx zenzic check all
```

Expected output:

```text
standalone · 1 file (1 docs, 0 assets) · 0.0s · 64 files/s

docs/guide.md:14:51  !  [Z107]  Self-referential anchor link: '[Setup](#setup)'
slugifies to its own fragment. Replace with a meaningful target or remove the
link.

    12  │  For advanced options, consult the reference documentation linked bel…
    13  │
    14  ❱  This page contains a self-referential anchor link: [Setup](#setup)
        │                                                     ^^^^^^^^^^^^^^^
    15  │
    16  │  ## Next Steps

────────────────────────────────────────────────────────────────────────────────

Summary:  x 0 errors  ! 1 warning  i 0 info  · 1 file with findings

Analysis complete: All statically-detectable links, credentials, and references
verified.
```

Exit code: `0`

---

## Interpreting the Output

The `Z107` finding indicates a **CIRCULAR_ANCHOR** issue.

This warning is raised when a link's text — after applying the same slug algorithm
the documentation engine uses for heading IDs — resolves to the same fragment as
the link target. Common causes:

- Copy-pasting a heading to use as link text without changing the `#anchor`
- Auto-generated "Back to top" links that point to the current section
- Table-of-contents entries where the link text exactly mirrors the heading

Metadata:

- **Scan Type:** `Rule Engine (built-in, always active)`
- **Severity:** `Warning`
- **Impact:** Deducts **1.0 DQS point** (structural category, weight 0.30).

---

## Resolve the Issue

Replace the circular link with either a meaningful external target or remove it:

```diff
- This page contains a self-referential anchor link: [Setup](#setup)
+ To jump to the next section, see [Next Steps](#next-steps).
```

---

## See Also

- [Z101 — Broken Links](z101-broken-links) — file-level link integrity.
- [Z102 — Anchor Missing](z102-anchor-missing) — the target fragment does not
  exist on the destination page.
- [Checks Reference — Z107](../../../reference/checks) — full rule specification.
