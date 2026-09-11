---
description: "Analysis of the z201-credentials fixture."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z201 — Credentials

**Z-Code:** `Z201 CREDENTIAL_SECRET` · **Engine:** `standalone` · **Exit:** `2`

---

## The Fixture

The fixture lives in `examples/z201-credentials/` in the Zenzic repository.
It contains documents demonstrating the `Z201` violation.

---

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z201-credentials
uvx zenzic check all
```

Expected output:

```text
✘ SECURITY BREACH DETECTED  [LIKELY PLACEHOLDER]
  ✘ Finding:    Secret detected (aws-access-key) — rotate immediately.
  ✘ Location:   docs/setup.md:15
  ✘ Credential:  AKIA************MPLE

  Action: Rotate this credential immediately and purge it from the repository
history.

standalone • 1 file (1 pages, 0 assets) • 0.0s

docs/setup.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/setup/'

────────────────────────────────────────────────────────────────────────────────

Summary:  ✘ 1 security breach  • 1 file impacted  ✘ 0 errors  ⚠ 1 warning  💡 0
info  • 1 file with findings

FAILED: Security breaches detected. Exit code 2 is mandatory.
DQS Final Score: 0/100 (Security Override — 1 non-suppressible finding detected)
Refer to https://zenzic.dev/reference/finding-codes/ for remediation · Try
'zenzic check --help' for options.
🔒 Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `2`

---

## Interpreting the Output

The `Z201` finding indicates a **CREDENTIAL_SECRET** issue.

This error or warning is raised by Zenzic when active secrets, API keys, tokens (such as AWS access keys, GitHub PATs, OpenAI API keys) are detected in raw documentation files or ref-def URLs. This is a critical security vulnerability that prevents publishing. In this specific example:

- **Scan Type:** `Credential Scanner`
- **Severity:** `Error (Non-suppressible)`
- **Impact:** A credential leak forces Zenzic to instantly collapse the DQS score to 0.0 and abort the execution with Exit Code 2. This gate cannot be bypassed with --exit-zero.

---

## Resolve the Issue

Exit code 2 triggers a critical build failure. Immediately rotate the exposed credential, purge the version control history, and inject secrets at runtime using environment variables instead of hardcoding them.

---

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
