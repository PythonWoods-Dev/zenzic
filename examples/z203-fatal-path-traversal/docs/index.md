<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z203 — Fatal Path Traversal Gallery Example

This page intentionally escapes the `docs/` boundary AND targets an OS
system directory, demonstrating **Z203 PATH_TRAVERSAL_FATAL** detection —
the fatal variant of Z202.

## Fatal Traversal Link

- [Passwd](../../../../etc/passwd) — this link escapes `docs/` and targets
  `/etc/`, an OS system directory → **Z203**, not Z202.

An ordinary boundary violation (escaping `docs/` toward a sibling directory
that is not an OS system path) stays Z202 and exits 1. Only a traversal
whose resolved path matches `/etc/`, `/root/`, `/var/`, `/proc/`, `/sys/`,
or `/usr/` is reclassified as Z203 and exits 3.

## What Zenzic Reports

```text
docs/index.md:12:  Z203  PATH_TRAVERSAL_FATAL  '../../../../etc/passwd' resolves outside the docs directory
```

Z203 is non-suppressible. Exit code 3. `zenzic check` treats it as a
security incident, distinct from Z201/Z204/Z205's "security breach" exit 2.

Run `zenzic check links` to reproduce the finding.
