---
description: "Analysis of the z115-stale-route-manifest scenario: a page absent from .zenzic-vsm.json triggers Z115 STALE_ROUTE_MANIFEST, and a correct link is reported broken."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z115 — Stale Route Manifest

**Z-Code:** `Z115 STALE_ROUTE_MANIFEST` · **Engine:** `prebuilt` · **Exit:** `1`

---

## Overview

The `prebuilt` engine does not work out your URLs. It reads them from
`.zenzic-vsm.json`, a routing table your site generator writes. That file is a
second copy of something the filesystem already knows, and second copies fall
behind: add a page, forget to re-run the generator, and the manifest no longer
describes your site.

What you see when that happens is *not* a complaint about the manifest. A page
the manifest does not list routes as `IGNORED`, so the link pointing at it is
reported unreachable — an error on a link you wrote correctly, about a page
that is right there on disk.

`Z115` is the finding that says which of the two is actually wrong.

---

## The Scenario

Two pages on disk:

```text
docs/index.md   — links to guide.md
docs/guide.md   — added after the manifest was last generated
```

And a manifest that knows about only one of them:

```json
// .zenzic-vsm.json
{
  "index.md": { "url": "/", "status": "REACHABLE" }
}
```

---

## Running the Check

The scenario ships as a fixture at `examples/z115-stale-route-manifest/`:

```bash
# Clone the Zenzic repository — no install required
cd examples/z115-stale-route-manifest
uvx zenzic check all
```

Expected output:

```text
prebuilt • 2 files (2 pages, 0 assets) • 0.0s • 62 files/s

docs/guide.md:1  ⚠  [Z115]  'guide.md' is not declared in the route manifest
(.zenzic-vsm.json), so it routes as IGNORED and every link to it is reported
unreachable. Re-run the generator that writes the manifest.

docs/index.md:10:16  ✘  [Z101]  'guide.md' resolves to '/guide/' which has VSM
status 'IGNORED' — the page exists but is not reachable via site navigation
(UNREACHABLE_LINK)

────────────────────────────────────────────────────────────────────────────────

Summary:  ✘ 1 error  ⚠ 1 warning  💡 0 info  • 2 files with findings

FAILED: Hard errors detected. Exit code 1 is mandatory.
```

Exit code: `1` — from the `Z101`, not from `Z115`, which is a warning.

---

## Interpreting the Output

Read the two findings together, and in this order:

- **`Z115` is the cause.** The manifest is missing a page.
- **`Z101` is the symptom.** A correct link points at a page that, as far as the
  routing table is concerned, has no place on the site.

Without `Z115` the run shows you only the `Z101`, and the repair it suggests —
edit the link — is the wrong one. The link was never the problem.

- **Scan Tier:** Link Validator / Routing Integrity
- **Severity:** `Warning` (1.0 point, Structural)

---

## Resolve the Issue

1. Re-run whatever generates `.zenzic-vsm.json`, and commit the updated file.
2. If the manifest is built in CI rather than committed, make sure that step
   runs **before** `zenzic check` in the same job. A manifest written after the
   check has no effect on it.
3. If nothing in your project writes a manifest at all, `prebuilt` is the wrong
   engine. Use `standalone`: it works each URL out from the path it just read,
   so there is no second copy to keep in sync.

---

## See Also

- [z101 — Broken Links](../z101-broken-links/) — the symptom this scenario produces.
- [Configure your adapter](../../../../how-to/configure-adapter/) — choosing between `prebuilt` and `standalone`.
- [Checks Reference](../../../../reference/checks/) — full rule specification.
