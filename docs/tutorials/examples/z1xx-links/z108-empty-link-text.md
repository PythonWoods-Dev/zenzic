---
description: "Analysis of the z108-empty-link-text fixture: a link whose label is empty, making it inaccessible to screen readers. Z-Code Z108 EMPTY_LINK_TEXT, exit 1."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z108 — Empty Link Text

**Z-Code:** `Z108 EMPTY_LINK_TEXT` · **Engine:** `standalone` · **Exit:** `1`

<Z108EmptyLinkText />

---

## The Fixture

The fixture lives in `examples/z108-empty-link-text/` in the Zenzic repository.
It contains two documents:

| File | Role |
| :--- | :---- |
| `docs/index.md` | Source — contains `[](guide.md)` at line 10 (empty label) |
| `docs/guide.md` | Target — exists on disk (ensures Z101 does not fire) |
| `.zenzic.toml` | Engine: `standalone`, `fail_under = 0` |

`docs/index.md` links to `guide.md` using `[](guide.md)` — the Markdown syntax
for a link with an empty label. The target file exists on disk (so Z101 does not
fire), but the link has no visible text. Screen readers announce it as the bare
word _"link"_ with no destination context, violating WCAG 2.1 §2.4.4 (Link
Purpose). Sighted users see an invisible, apparently blank bullet point.

---

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z108-empty-link-text
uvx zenzic check links
```

Expected output:

```text
standalone - 2 files (2 docs, 0 assets) - 0.0s - 120 files/s

docs/guide.md:4  !  [Z502]  Page has only 25 words (minimum 50).

    2  │  <!-- SPDX-License-Identifier: Apache-2.0 -->
    3  │
    4  ❱  # Guide
    5  │
    6  │  This guide page exists on disk so that `[](guide.md)` in `index.md`
does not

docs/index.md:10:2  x  [Z108]  link label is empty or whitespace-only

     8  │  ## Empty Link
     9  │
    10  ❱  - [TODO: ADD LABEL](guide.md) — empty label (no visible text for screen readers) →
**Z108**
        │
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    11  │
    12  │  ## What Zenzic Reports

────────────────────────────────────────────────────────────────────────────────

Summary:  x 1 error  ! 1 warning  i 0 info  - 2 files with findings

FAILED: Hard errors detected. Exit code 1 is mandatory.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `1`

---

## Interpreting the Output

The `Z108` finding indicates a **EMPTY_LINK_TEXT** issue.

This error or warning is raised by Zenzic when a markdown link has empty or whitespace-only label text (e.g., `[](/path)`). This is a accessibility violation, as screen readers cannot announce any meaningful description to the user. In this specific example:

- **Scan Type:** `Link Validator`
- **Severity:** `Error`
- **Impact:** Empty link text violates accessibility standards and incurs a DQS deduction of 1.0 point.

---

## Resolve the Issue

Exit code 1. Add descriptive, accessible label text inside the Markdown link brackets.

---

## See Also

- [z101 — Broken Links](z101-broken-links) — the target file does not exist on disk.
- [z105 — Absolute Path](z105-absolute-path) — the link uses a non-portable absolute path.
- [z403 — Missing Alt Text](../../examples/z4xx-topology/z403-missing-alt) — the same accessibility principle applied to images.
- [Checks Reference](../../../reference/checks) — full rule specification.
