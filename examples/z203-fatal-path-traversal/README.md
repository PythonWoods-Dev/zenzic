<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z203 PATH_TRAVERSAL_FATAL — Gallery Example

**Category:** Z2xx Security
**Expected exit:** 3 (security incident — non-suppressible)

## What this demonstrates

`docs/index.md` contains `[Passwd](../../../../etc/passwd)` — a link that
both escapes the `docs/` directory boundary and resolves into an OS system
directory (`/etc/`). Zenzic classifies traversal intent by regex-scanning
the raw href for `/etc/`, `/root/`, `/var/`, `/proc/`, `/sys/`, or `/usr/`
(see `_classify_traversal_intent` in `zenzic.core.validator`); a match
upgrades the finding from the ordinary Z202 boundary violation to
**Z203 PATH_TRAVERSAL_FATAL**.

Z203 is **non-suppressible** (cannot be silenced with inline `zenzic: ignore`)
and exits with code **3** — the only finding code with this exit code; every
other non-suppressible Z2xx code (Z201, Z204, Z205) exits 2.

## Run it

```bash
zenzic lab z203
# or directly:
zenzic check links
```

## Expected output

```text
docs/index.md:12:  Z203  PATH_TRAVERSAL_FATAL  '../../../../etc/passwd' resolves outside the docs directory
```

Exit code **3**.

## Fix

Remove the traversal link. If the target is a legitimate internal resource,
relocate it under `docs/` and use a relative path.
