<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z204 — Forbidden Term Gallery Example

This page intentionally mentions a term declared in `.zenzic.local.toml`,
demonstrating **Z204 FORBIDDEN_TERM** detection.

## Forbidden Term Occurrence

The development team is building **ProjectX** — our internal codename for the
next-generation platform. This page was written before the public launch and
still contains the internal codename that must not appear in published docs.

The staging environment is available at `staging.internal.corp` for QA purposes.

## What Zenzic Reports

```text
docs/index.md:11:  Z204  FORBIDDEN_TERM  Forbidden term detected — remove from documentation: 'ProjectX'
```

Z204 is non-suppressible. Exit code 2. The CLI shows "POLICY VIOLATION DETECTED".

Run `zenzic check all` to reproduce the finding.

Forbidden-term scanning catches internal codenames and staging hostnames
before they leak into published documentation, where they would otherwise
require an embarrassing retroactive redaction.
