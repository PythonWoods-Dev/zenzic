---
description: "Walk through the z406-nav-contract fixture: mkdocs.yml declares extra.alternate with link /it/ but no Italian pages exist, triggering Z406 NAV_CONTRACT."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z406 — Nav Contract

**Z-Code:** `Z406 NAV_CONTRACT` · **Engine:** `mkdocs` · **Exit:** `1`

---

## The Fixture

The fixture lives at `examples/z406-nav-contract/` in the Zenzic repository.
It uses the **MkDocs** engine.

`mkdocs.yml` declares `extra.alternate` with an Italian locale link `/it/`,
but there are no Italian source pages (no `docs/*.it.md` or `docs/it/` subtree).
The route `/it/` is therefore **absent from the Virtual Site Map**:

```yaml title="examples/z406-nav-contract/mkdocs.yml"
site_name: My Project
extra:
  alternate:
    - name: English
      link: /
      lang: en
    - name: Italiano
      link: /it/
      lang: it
```

```toml title="examples/z406-nav-contract/.zenzic.toml"
docs_dir = "docs"
fail_under = 0

[build_context]
engine = "mkdocs"
```

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z406-nav-contract
uvx zenzic check all
```

Expected output:

```text
mkdocs · 2 files (2 docs, 0 assets) · 0.0s · 109 files/s

docs/(nav)  x  [Z406]  mkdocs.yml extra.alternate[it]: link '/it/' does not
correspond to any URL the build engine will generate. The Virtual Site Map
contains no entry for '/it/'. Use a path that maps to an existing source file
(e.g. '/index.it/' for the it home page).

────────────────────────────────────────────────────────────────────────────────

Summary:  x 1 error  ! 0 warnings  i 0 info  · 1 file with findings

FAILED: Hard errors detected. Exit code 1 is mandatory.
```

Exit code: `1`

---

## Interpreting the Output

The `Z406` finding indicates a **NAV_CONTRACT** violation.

Zenzic builds a **Virtual Site Map (VSM)** — the complete set of URLs the
documentation engine will generate from the source tree. Every URL declared in
`extra.alternate` must exist in the VSM; if it does not, clicking the language
switcher produces a 404:

- **Scan Type:** `Nav Contract Checker (mkdocs engine)`
- **Severity:** `Warning`
- **Impact:** Deducts **2.0 DQS points** (brand governance category, weight 0.25).

---

## Resolve the Issue

Option A — Create the missing locale content:

```bash
# Create the Italian home page (MkDocs suffix-locale convention)
cp docs/index.md docs/index.it.md
# Translate the content, then re-run zenzic check all
```

Option B — Remove the broken alternate entry:

```diff
extra:
  alternate:
    - name: English
      link: /
      lang: en
-   - name: Italiano
-     link: /it/
-     lang: it
```

---

## See Also

  files between locales.

- [Z404 — Config Asset Missing](z404-config-asset-missing) — infrastructure
  asset referenced in config not found.
- [Checks Reference — Z406](../../../reference/checks) — full rule specification.
