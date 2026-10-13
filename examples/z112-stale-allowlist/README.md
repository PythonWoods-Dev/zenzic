<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z112 STALE_ALLOWLIST_ENTRY — Gallery Example

**Category:** Z1xx Link Integrity
**Expected exit:** 0 (warnings only) / 1 (under `--strict` or if `strict = true` in config)

## What this demonstrates

`.zenzic.toml` declares `absolute_path_allowlist = ["/legacy/unused/path/"]`.
However, none of the links scanned in `docs/` match this prefix. Zenzic alerts the user that this allowlist entry is stale, emitting **Z112 STALE_ALLOWLIST_ENTRY** targeting line 1 of the configuration file.

## Run it

```bash
zenzic lab z112
# or directly:
zenzic check links --strict
```

## Expected output

```text
.zenzic.toml:1: Stale absolute_path_allowlist entry: '/legacy/unused/path/' is never referenced in links.
```

## Real-world fix

Open `.zenzic.toml` (or `pyproject.toml`) and remove the unused `"/legacy/unused/path/"` entry from `absolute_path_allowlist`.
