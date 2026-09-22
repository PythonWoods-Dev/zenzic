<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z203 — Fatal Path Traversal Gallery Example

This page intentionally escapes the `docs/` boundary AND targets an OS
system directory, demonstrating **Z203 PATH_TRAVERSAL_FATAL** detection —
the fatal variant of Z202.

## Fatal Traversal Link

- [Passwd](../../../../etc/passwd) — this link escapes `docs/` and targets
  `/etc/`, an OS system directory → **Z203**, not Z202.

## The Same Target, Percent-Encoded

- [Encoded](..%2f..%2f..%2f..%2fetc%2fpasswd) — `%2f` is a slash to everything
  that resolves the link, so this reaches the same file → **Z203** as well.

The check decodes before it classifies, so an encoded spelling cannot hide a
traversal. Repeated encoding (`..%252f`), mixed-case escapes (`%2F`) and
backslash separators are folded the same way.

An ordinary boundary violation (escaping `docs/` toward a sibling directory
that is not an OS system path) stays Z202 and exits 1. A traversal is
reclassified as Z203 when the path it *lands* on is a system root — `/etc/`,
`/root/`, `/var/`, `/proc/`, `/sys/`, `/usr/`, `/bin/`, `/sbin/`, `/boot/`,
`/dev/`, and the Windows equivalents (`windows`, `winnt`, `system32`,
`programdata`). Landing matters, not spelling: `../../guide/usr/manual.md`
mentions `usr` but arrives inside the docs tree and is not Z203.

## What Zenzic Reports

```text
docs/index.md:12:  Z203  PATH_TRAVERSAL_FATAL  '../../../../etc/passwd' resolves outside the docs directory
```

Z203 is non-suppressible. Exit code 3. `zenzic check` treats it as a
security incident, distinct from Z201/Z204/Z205's "security breach" exit 2.

Run `zenzic check links` to reproduce the finding.
