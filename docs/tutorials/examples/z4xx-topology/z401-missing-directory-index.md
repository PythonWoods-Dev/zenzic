---
description: "Walk through the z401-missing-directory-index fixture: a guide directory missing index.md, triggering Z401 MISSING_DIRECTORY_INDEX."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z401 — Missing Directory Index

**Z-Code:** `Z401 MISSING_DIRECTORY_INDEX` · **Engine:** `zensical` · **Exit:** `0`

<Z401MissingDirectoryIndex />

---

## The Fixture

The fixture lives at `examples/z401-missing-directory-index/` in the Zenzic
repository. It uses the **Zensical** engine (requires `zensical.toml`).

The `docs/guide/` directory contains `page.md` but has **no `index.md`**:

```text
docs/
  guide/
    page.md   ✓ exists
    index.md  ✘ missing
```

When the site is built, visiting `/guide/` will return a **404** because no
page maps to that directory URL:

```toml title="examples/z401-missing-directory-index/.zenzic.toml"
docs_dir = "docs"
fail_under = 0

[build_context]
engine = "zensical"
```

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z401-missing-directory-index
uvx zenzic check all --show-info
```

!!! info
    Z401 is an **info** finding — it is suppressed by default to keep CI output
    concise. Pass `--show-info` to make it visible.

Expected output:

```text
zensical · 1 file (1 docs, 0 assets) · 0.0s · 68 files/s

docs/guide  i  [Z401]  Directory contains Markdown files but has no index page
— the directory URL may return a 404.

────────────────────────────────────────────────────────────────────────────────

Summary:  x 0 errors  ! 0 warnings  i 1 info  · 1 file with findings

Analysis complete: All statically-detectable links, credentials, and references
verified.
```

Exit code: `0`

---

## Interpreting the Output

The `Z401` finding indicates a **MISSING_DIRECTORY_INDEX** issue.

Documentation engines that use directory-style URLs (e.g., `/guide/` instead of
`/guide.html`) require each directory that is browsable to have an `index.md`
(or `index.md`) as its landing page. Without one, the build engine may silently
omit the directory URL or return a 404:

> **Standalone Mode:** When using the `standalone` engine, Zenzic accepts both `index.md` and `README.md` as valid directory indices, adapting natively to standard GitHub/GitLab repository structures.

- **Scan Type:** `Structure Validator (zensical engine)`
- **Severity:** `Info`
- **Impact:** Informational only — deducts **no DQS points**.

---

## Resolve the Issue

Create `docs/guide/index.md` with a landing page for the section:

```bash
touch docs/guide/index.md
```

Or rename `page.md` to `index.md` if it is the only page in the directory:

```bash
mv docs/guide/page.md docs/guide/index.md
```

---

## See Also

- [Z402 — Orphan Page](z402-orphan-page) — page exists but is not in navigation.
- [Z403 — Missing Alt](z403-missing-alt) — image lacks accessibility alt text.
- [Checks Reference — Z401](../../../reference/checks) — full rule specification.
