---
description: "Walk through the z109-external-link-broken fixture: an external URL that cannot be reached, consolidated and reported under Z101 LINK_BROKEN by the current engine."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z109 — External Link Broken

**Cataloged as:** `Z109 EXTERNAL_LINK_BROKEN` · **Emitted as:** `Z101 LINK_BROKEN` · **Engine:** `standalone` · **Exit:** `1`

---

## The Fixture

The fixture lives at `examples/z109-external-link-broken/` in the Zenzic repository.
The source document is `docs/index.md`, which contains an external link pointing to a URL that returns an HTTP error or does not exist:

| Line | Link | Target | Exists? |
| :--: | :--- | :----- | :-----: |
| 7    | `[Broken Link](https://this-domain-does-not-exist-at-all-xyz.com)` | `https://this-domain-does-not-exist-at-all-xyz.com` | ✘ |

Neither the domain exists nor does it return a success status code.
`Z109 EXTERNAL_LINK_BROKEN` is defined in the finding-codes catalog for this
condition, but the current engine reports all unreachable links — internal or
external — under the consolidated `Z101 LINK_BROKEN` code. Zenzic fires
`Z101` for this broken external link.

```toml title="examples/z109-external-link-broken/.zenzic.toml"
docs_dir = "docs"
fail_under = 0

[build_context]
engine = "standalone"
```

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z109-external-link-broken
uvx zenzic check links --strict   # external URLs are only fetched under --strict
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.2s • 5 files/s

docs  ✘  [Z101]
<abs-path>/docs/index.md:7: external link
'https://this-domain-does-not-exist-at-all-xyz.com' — connection error: [Errno
-2] Name or service not known

────────────────────────────────────────────────────────────────────────────────

Summary:  ✘ 1 error  ⚠ 0 warnings  💡 0 info  • 1 file with findings

FAILED: Hard errors detected. Exit code 1 is mandatory.
Try 'zenzic check links --help' for options.
```

Exit code: `1`

Two details this output makes visible. The finding is reported under `Z101`, not
`Z109`: external-link failures are consolidated into the broken-link code at
report time. And the location is written as an absolute path rather than the
`docs/index.md:7` form used everywhere else, because an external-link error is
attached to the documentation root rather than to the file — the `<abs-path>`
placeholder above stands for your own checkout's path.

---

## Interpreting the Output

The `Z101` finding indicates a **LINK_BROKEN** issue (this scenario is cataloged as `Z109 EXTERNAL_LINK_BROKEN`, but the engine reports it under the consolidated `Z101` code — see [Z109 rule specification](../../../rules/Z109.md)).

This error is raised by Zenzic when an external link references a URL that cannot be resolved, timed out, or returned an HTTP status error (e.g., 404, 500). In this specific example:

- **Scan Type:** `Link Validator`
- **Severity:** `Error`
- **Impact:** Broken external links degrade the user experience and reduce the Documentation Quality Score (DQS). As a `Z101 LINK_BROKEN` finding, this deducts a penalty of 8.0 points (the `Z101` penalty; `Z109`'s cataloged 3.0-point penalty does not apply since the engine does not emit `Z109`).

---

## Resolve the Issue

Correct the external link target to a valid URL, or remove the link if the resource is no longer available.

---

## See Also

- [z101 — Broken Links](z101-broken-links) — the internal-link variant of link integrity.
- [Checks Reference — Z109](../../../reference/checks) — full rule specification.
