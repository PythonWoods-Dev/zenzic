---
sidebar_position: 1
sidebar_label: "Z620 - Stale Global Suppression"
description: "Walk through the z620-stale-global-suppression fixture: an unused global directory policy triggering Z620 at exit code 1."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z620 — Stale Global Suppression

**Z-Code:** `Z620 STALE_GLOBAL_SUPPRESSION` · **Engine:** `standalone` · **Exit:** `1`

## The Fixture

The fixture lives at `examples/z620-stale-global-suppression/` in the Zenzic repository.
The source `docs/clean-page.md` contains no broken links, but `.zenzic.toml` defines a global policy to suppress `Z101` on it:

```toml title="examples/z620-stale-global-suppression/.zenzic.toml"
docs_dir = "docs"
fail_under = 0

[build_context]
engine = "standalone"

[governance.directory_policies]
"docs/clean-page.md" = ["Z101"]
```

Because `Z101` is never triggered by `clean-page.md`, the policy is "stale" or "dead". Zenzic flags this configuration debt with `Z620`.

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z620-stale-global-suppression
uvx zenzic check all --strict
```

Expected output:

```text
.zenzic.toml:1  !  [Z620]  Global policy 'docs/clean-page.md' = ['Z101'] was never used to suppress a finding. Remove the dead configuration.
```

Exit code: `1`

## Interpreting the Output

The `Z620` finding indicates a **STALE_GLOBAL_SUPPRESSION** issue.

This warning is raised by Zenzic when an entry in `directory_policies`, `excluded_file_patterns`, or `excluded_external_urls` is never utilized to suppress an actual finding during the scan.

- **Scan Type:** `All`
- **Severity:** `Warning` (can be promoted to `Error` via `--strict`)
- **Impact:** Accumulation of dead policies creates configuration debt and obscures the true perimeter.

## Resolve the Issue

The remedy to Z620 is always to remove the offending line or policy block from `.zenzic.toml`.
