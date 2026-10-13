<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z203 PATH_TRAVERSAL_FATAL — Gallery Example

**Category:** Z2xx Security
**Expected exit:** 3 (security incident — non-suppressible)

## What this demonstrates

`docs/index.md` contains `[Passwd](../../../../etc/passwd)` — a link that
both escapes the `docs/` directory boundary and resolves into an OS system
directory (`/etc/`) — and `[Encoded](..%2f..%2f..%2f..%2fetc%2fpasswd)`, the
same destination spelled with percent-encoded separators.

Zenzic classifies traversal intent by *destination*: the href is percent-
decoded (repeatedly, so `..%252f` is covered too), backslashes are folded to
slashes, the path is normalised, and the leading escape hops are dropped. If
what remains starts on a system root — `etc`, `root`, `var`, `proc`, `sys`,
`usr`, `bin`, `sbin`, `boot`, `dev`, or the Windows names `windows`, `winnt`,
`system32`, `programdata` — the finding is upgraded from the ordinary Z202
boundary violation to **Z203 PATH_TRAVERSAL_FATAL** (see
`_classify_traversal_intent` in `zenzic.core.validator`). Classification does
not substring-search the text, so `../../guide/usr/manual.md` — which mentions
`usr` but lands inside the docs tree — is not Z203.

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
docs/index.md:12  ✘  [Z203]  '../../../../etc/passwd' resolves outside the docs directory
docs/index.md:17  ✘  [Z203]  '..%2f..%2f..%2f..%2fetc%2fpasswd' resolves outside the docs directory
```

Two findings, one destination, two spellings. Exit code **3**.

## Fix

Remove the traversal link. If the target is a legitimate internal resource,
relocate it under `docs/` and use a relative path.
