---
description: "Walk through the z109-external-link-broken fixture: an external URL that cannot be reached, triggering Z109 EXTERNAL_LINK_BROKEN."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z109 — External Link Broken

**Z-Code:** `Z109 EXTERNAL_LINK_BROKEN` · **Engine:** `standalone` · **Exit:** `1`

<Z109ExternalLinkBroken />

## The Fixture

The fixture lives at `examples/z109-external-link-broken/` in the Zenzic repository.
The source document is `docs/index.md`, which contains an external link pointing to a URL that returns an HTTP error or does not exist:

| Line | Link | Target | Exists? |
| :--: | :--- | :----- | :-----: |
| 7    | `[Broken Link](https://this-domain-does-not-exist-at-all-xyz.com)` | `https://this-domain-does-not-exist-at-all-xyz.com` | ✘ |

Neither the domain exists nor does it return a success status code.
Zenzic fires Z109 for this broken external link.

```toml title="examples/z109-external-link-broken/.zenzic.toml"
docs_dir = "docs"
fail_under = 0

[build_context]
engine = "standalone"
```

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z109-external-link-broken
uvx zenzic check links
```

Expected output:

```text
standalone - 1 file (1 docs, 0 assets) - 0.0s - 65 files/s

docs/index.md:7:2  x  [Z109]  external link 'https://this-domain-does-not-exist-at-all-xyz.com' is broken

     5  │
     6  │  Here is a broken external link:
     7  ❱  - [Broken Link](https://this-domain-does-not-exist-at-all-xyz.com)
        │    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
     8  │

────────────────────────────────────────────────────────────────────────────────

Summary:  x 1 errors  ! 0 warnings  i 0 info  - 1 file with findings

FAILED: Hard errors detected. Exit code 1 is mandatory.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `1`

## Interpreting the Output

The `Z109` finding indicates an **EXTERNAL_LINK_BROKEN** issue.

This error is raised by Zenzic when an external link references a URL that cannot be resolved, timed out, or returned an HTTP status error (e.g., 404, 500). In this specific example:

- **Scan Type:** `Link Validator`
- **Severity:** `Error`
- **Impact:** Broken external links degrade the user experience and reduce the Documentation Quality Score (DQS) by deducting a penalty of 3.0 points.

## Resolve the Issue

Correct the external link target to a valid URL, or remove the link if the resource is no longer available.

## See Also

- [z101 — Broken Links](z101-broken-links) — the internal-link variant of link integrity.
- [Checks Reference — Z109](../../../reference/checks) — full rule specification.
