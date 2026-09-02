---
description: "Walk through the z404-config-asset-missing fixture: mkdocs.yml logo file does not exist, triggering Z404 CONFIG_ASSET_MISSING."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z404 — Config Asset Missing

**Z-Code:** `Z404 CONFIG_ASSET_MISSING` · **Engine:** `mkdocs` · **Exit:** `0`

---

## The Fixture

The fixture lives at `examples/z404-config-asset-missing/` in the Zenzic
repository. It uses the **MkDocs** engine.

`mkdocs.yml` declares `theme.logo: assets/logo.svg` but `docs/assets/logo.svg`
does not exist on disk:

```yaml title="examples/z404-config-asset-missing/mkdocs.yml"
site_name: My Project
theme:
  name: material
  logo: assets/logo.svg
```

```toml title="examples/z404-config-asset-missing/.zenzic.toml"
docs_dir = "docs"
fail_under = 0

[build_context]
engine = "mkdocs"
```

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z404-config-asset-missing
uvx zenzic check all
```

Expected output:

```text
mkdocs · 2 files (2 docs, 0 assets) · 0.0s · 116 files/s

docs/docs/assets/logo.svg  !  [Z404]  logo asset not found on disk:
'docs/assets/logo.svg' (declared as theme.logo: 'assets/logo.svg' in mkdocs.yml)
[Z404]

────────────────────────────────────────────────────────────────────────────────

Summary:  x 0 errors  ! 1 warning  i 0 info  · 1 file with findings

Analysis complete: All statically-detectable links, credentials, and references
verified.
```

Exit code: `0`

---

## Interpreting the Output

The `Z404` finding indicates a **CONFIG_ASSET_MISSING** issue.

This warning is raised when the build engine configuration (e.g., `mkdocs.yml`
or `zensical.toml`) references a local asset file by
path, but that file does not exist on disk. The configuration is valid YAML/TOML,
but the asset it points to is absent:

- **Scan Type:** `Config Asset Checker (engine-specific)`
- **Severity:** `Warning`
- **Impact:** Deducts **3.0 DQS points** (brand governance category, weight 0.25).

Checked fields in MkDocs Material:

- `theme.logo` — resolved relative to `docs_dir`
- `theme.favicon` — resolved relative to `docs_dir`

---

## Resolve the Issue

Create the missing asset file:

```bash
mkdir -p docs/assets
# Add your logo SVG:
cp my-logo.svg docs/assets/logo.svg
```

Or update `mkdocs.yml` to point to an existing file:

```diff
theme:
  name: material
- logo: assets/logo.svg
+ logo: assets/brand-icon.png
```

---

## See Also

- [Z405 — Unused Assets](z405-unused-assets) — the inverse: a file exists but is never referenced.
- [Z402 — Orphan Page](z402-orphan-page) — page exists but is absent from navigation.
- [Checks Reference — Z404](../../../reference/checks) — full rule specification.
