---
description: "Analysis of the z201-credentials fixture."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z201 — Credentials

**Z-Code:** `Z201 CREDENTIAL_SECRET` · **Engine:** `standalone` · **Exit:** `2`

<Z201Credentials />

## The Fixture

The fixture lives in `examples/z201-credentials/` in the Zenzic repository.
It contains documents demonstrating the `Z201` violation.

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z201-credentials
uvx zenzic check all
```

Expected output:

```text
✘ SECURITY BREACH DETECTED
  x Finding:    Secret detected (aws-access-key) — rotate immediately.
  x Location:   docs/setup.md:15
  x Credential:  AKIA************MPLE

  Action: Rotate this credential immediately and purge it from the repository
history.

standalone - 1 file (1 docs, 0 assets) - 0.0s - 58 files/s

────────────────────────────────────────────────────────────────────────────────

Summary:  x 1 security breach  - 1 file impacted  x 0 errors  ! 0 warnings  i 0
info  - 0 files with findings

FAILED: Security breaches detected. Exit code 2 is mandatory.
Refer to ../../../reference/finding-codes.md for remediation · Try
'zenzic check --help' for options.
[ Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `2`

## Interpreting the Output

The `Z201` finding indicates a **CREDENTIAL_SECRET** issue.

This error or warning is raised by Zenzic when active secrets, API keys, tokens (such as AWS access keys, GitHub PATs, OpenAI API keys) are detected in raw documentation files or ref-def URLs. This is a critical security vulnerability that prevents publishing. In this specific example:

- **Scan Type:** `Credential Scanner`
- **Severity:** `Error (Non-suppressible)`
- **Impact:** A credential leak forces Zenzic to instantly collapse the DQS score to 0.0 and abort the execution with Exit Code 2. This gate cannot be bypassed with --exit-zero.

## Resolve the Issue

Exit code 2 triggers a critical build failure. Immediately rotate the exposed credential, purge the version control history, and inject secrets at runtime using environment variables instead of hardcoding them.

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
