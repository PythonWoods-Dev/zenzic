---
description: "Analysis of the z204-forbidden-term fixture."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z204 — Forbidden Term

**Z-Code:** `Z204 FORBIDDEN_TERM` · **Engine:** `standalone` · **Exit:** `2`

---

## The Fixture

The fixture lives in `examples/z204-forbidden-term/` in the Zenzic repository.
It contains documents demonstrating the `Z204` violation.

---

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/z204-forbidden-term
uvx zenzic check all
```

Expected output:

```text
✘ POLICY VIOLATION DETECTED
  ✘ Finding:    Forbidden term detected — remove from documentation: 'ProjectX'
  ✘ Location:   docs/index.md:11
  ✘ Term:        ProjectX

  Action: Remove this term from the documentation or update the
forbidden_patterns list in .zenzic.local.toml.

✘ POLICY VIOLATION DETECTED
  ✘ Finding:    Forbidden term detected — remove from documentation:
'staging.internal.corp'
  ✘ Location:   docs/index.md:15
  ✘ Term:        staging.internal.corp

  Action: Remove this term from the documentation or update the
forbidden_patterns list in .zenzic.local.toml.

✘ POLICY VIOLATION DETECTED
  ✘ Finding:    Forbidden term detected — remove from documentation: 'ProjectX'
  ✘ Location:   docs/index.md:20
  ✘ Term:        ProjectX

  Action: Remove this term from the documentation or update the
forbidden_patterns list in .zenzic.local.toml.

standalone • 1 file (1 pages, 0 assets) • 0.0s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'

────────────────────────────────────────────────────────────────────────────────

Summary:  ✘ 3 policy violations  • 1 file impacted  ✘ 0 errors  ⚠ 1 warning  💡
0 info  • 1 file with findings

FAILED: Policy violations detected. Exit code 2 is mandatory.
DQS Final Score: 0/100 (Security Override — 3 non-suppressible findings
detected)
Refer to https://zenzic.dev/reference/finding-codes/ for remediation · Try
'zenzic check --help' for options.
🔒 Suppression Audit: 0/30 (inline: 0, per-file: 0)
```

Exit code: `2`

---

## Interpreting the Output

The `Z204` finding indicates a **FORBIDDEN_TERM** issue.

This error or warning is raised by Zenzic when a project-specific forbidden term or confidential internal codename is detected in the documentation. These terms are defined in `.zenzic.local.toml` under `forbidden_patterns` to prevent accidental public disclosure of sensitive information. In this specific example:

- **Scan Type:** `Privacy Gate`
- **Severity:** `Error (Non-suppressible)`
- **Impact:** Forbidden terms trigger an immediate halt with Exit Code 2 and zero out the security status of the project.

---

## Resolve the Issue

Exit code 2 triggers a policy breach. Remove the blacklisted term from the markdown text or update the forbidden term lists in your local environment configuration.

---

## See Also

- [Checks Reference](../../../reference/checks) — full rule specification.
