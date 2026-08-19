---
description: "Analysis of the z105-absolute-path fixture: a link using an absolute path starting with '/', breaking host-path portability. Z-Code Z105 ABSOLUTE_PATH, exit 1."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z105 — Absolute Path

**Z-Code:** `Z105 ABSOLUTE_PATH` · **Engine:** `standalone` · **Exit:** `1`

<Z105AbsolutePath />

---

## The Fixture

The fixture lives in `examples/z105-absolute-path/` in the Zenzic repository.
It contains a single document:

| File | Role |
| :--- | :---- |
| `docs/index.md` | Source — contains `[Guide](/guide)` at line 10 |
| `.zenzic.toml` | Engine: `standalone`, `fail_under = 0` |

`docs/index.md` links to `/guide` using an absolute path. Absolute paths are
resolved from the server root: when a site is hosted under a subdirectory
(e.g., `https://example.com/my-docs/`), the link `/guide` resolves to
`https://example.com/guide` — not to `https://example.com/my-docs/guide`.
This silent mis-resolution makes the documentation non-portable across hosting
environments such as GitHub Pages project sites or CDN subdirectory deployments.

---

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z105-absolute-path
uvx zenzic check links
```

Expected output:

```text
standalone - 1 file (1 docs, 0 assets) - 0.0s - 66 files/s

docs/index.md:10:2  x  [Z105]  '/guide' uses an absolute path — use a relative
path (e.g. '../' or './') instead; absolute paths break portability when the
site is hosted in a subdirectory

     8  │  ## Absolute Path Link
     9  │
    10  ❱  - [Guide](/guide) — uses `/guide` (absolute) instead of `guide.md`
(relative) → **Z105**
        │    ^^^^^^^^^^^^^^^
    11  │
    12  │  ## What Zenzic Reports

────────────────────────────────────────────────────────────────────────────────

Summary:  x 1 error  ! 0 warnings  i 0 info  - 1 file with findings

FAILED: Hard errors detected. Exit code 1 is mandatory.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `1`

---

## Interpreting the Output

The `Z105` finding indicates a **ABSOLUTE_PATH** issue.

This error or warning is raised by Zenzic when a link uses an absolute path (starting with `/` or pointing to a full system path) instead of a relative path. This violates portability constraints, as the documentation will fail to render correctly when deployed to different server subpaths or preview environments. In this specific example:

- **Scan Type:** `Link Validator`
- **Severity:** `Error`
- **Impact:** Absolute paths reduce documentation portability, incurring a DQS deduction of 2.0 points.

---

## Resolve the Issue

Exit code 1. Replace the root-relative path link with a document-relative path link (e.g., use `../guide/setup.md` instead of `/guide/setup.md`).

---

## See Also

- [z101 — Broken Links](z101-broken-links) — the target file does not exist on disk.
- [z108 — Empty Link Text](z108-empty-link-text) — the link label is empty, breaking screen reader accessibility.
- [z202 — Path Traversal](../../examples/z2xx-security/z202-path-traversal) — a link that escapes the `docs/` directory boundary.
- [Checks Reference](../../../reference/checks) — full rule specification.
