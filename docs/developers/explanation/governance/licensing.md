---

description: "Zenzic compliance and licensing policy based on Apache-2.0 and REUSE 3.3 specifications."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Zenzic Compliance: Apache-2.0 + REUSE 3.3

> *"Every file in Zenzic carries the cryptographic signature of its license.
> There are no dark corners."*

---

## 1. The License

Zenzic is distributed as free and open-source software under the **Apache License 2.0**. This is not a policy choice —
it is an engineering commitment. It permits free use, modification, and distribution in all environments, including commercial contexts. Apache-2.0 provides:

| Permission | Details |
| :--- | :--- |
| ✅ Commercial use | No restrictions |
| ✅ Modification | Fork, patch, extend |
| ✅ Distribution | Redistribute under same license |
| ✅ Patent grant | Explicit patent license from all contributors |

**Conditions:**

- Preserve the `LICENSE` and `NOTICE` files in distributions.
- State significant changes in modified versions.

**Full text:** `LICENSE` file at the root of each Zenzic repository.

---

## 2. The License Signature — SPDX + REUSE 3.3

Every source file in Zenzic carries an **SPDX header** — a machine-readable
declaration of authorship and license:

```python
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
```

This is not a comment. It is a **license signature** — machine-parseable by any
REUSE 3.3-compliant tool, including `reuse lint`.

Files that cannot carry an inline header — because the format has no comment
syntax, or because the comment would appear in rendered output — are covered
instead by `REUSE.toml` annotation blocks:

```toml title="REUSE.toml (excerpt)"
# JSON files (no comment syntax)
[[annotations]]
path = [".zenzic-score.json", "coverage.json", "zenzic-output.schema.json"]
SPDX-FileCopyrightText = "2026 PythonWoods <dev@pythonwoods.dev>"
SPDX-License-Identifier = "Apache-2.0"

# Root Markdown prose — inline SPDX would appear in rendered output
[[annotations]]
path = ["README.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md"]
SPDX-FileCopyrightText = "2026 PythonWoods <dev@pythonwoods.dev>"
SPDX-License-Identifier = "Apache-2.0"

# Binary/font assets
[[annotations]]
path = "docs/assets/**"
precedence = "aggregate"
SPDX-FileCopyrightText = "2026 PythonWoods <dev@pythonwoods.dev>"
SPDX-License-Identifier = "Apache-2.0"
```

**Coverage strategy:**

| Component | Method |
| :--- | :--- |
| Python source files | Per-file SPDX header |
| Shell scripts | Per-file SPDX header |
| Configuration (TOML, YAML) | Per-file SPDX header |
| Documentation pages (`docs/**/*.md`) | Per-file SPDX header (HTML comment) — see this page's own header above |
| Root-level prose (`README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, etc.) | `REUSE.toml` bulk declaration — inline SPDX would render visibly in these files |
| JSON files, `uv.lock`, extension-less files (`LICENSE`, `NOTICE`) | `REUSE.toml` bulk declaration (no comment syntax) |
| Binary/font assets (`docs/assets/**`) | `REUSE.toml` bulk declaration |

---

## 3. The Single Gate of Truth

```bash
uv run reuse lint
```

This is the **only authorised compliance verification command.** It:

1. Parses every SPDX header in every file.
2. Validates all `REUSE.toml` bulk declarations.
3. Reports any file without coverage as a compliance failure.
4. Returns exit 0 only when 100% of files have a declared license.

**Expected output:**

```text
Congratulations! Your project is compliant with version 3.3 of the REUSE Specification.
```

This gate runs in:

- Its own dedicated pre-commit hook (`reuse`, hook 5 of 8 — `repo: fsfe/reuse-tool`, commit-time)
- `just verify` (hook 8 of 8, `just-verify` — pre-push only), which transitively re-runs the full commit-time hook chain, `reuse` included

It is unrelated to the Zenzic Guard hook (hook 7 of 8, `zenzic-guard`) — that hook is a secret scanner over staged Markdown/MDX, not a license-compliance check.

Any PR that fails `uv run reuse lint` does not merge.

> **Operational note:** if a reference endpoint times out in the final guard,
> keep the document content unchanged and use the local permalink instead of an
> external URL. For the adapter guide, link to
> `/developers/how-to/implement-adapter` so the guard checks the real site route
> without depending on a remote fetch.

---

## 4. Contributor Policy — No CLA, Multi-Author Copyright

Zenzic uses the **multi-author copyright model**. No Contributor License Agreement
(CLA) is required.

| Scenario | Action |
| :--- | :--- |
| New file (any contributor) | Add your own SPDX copyright line |
| Small change (< 10 lines) | Keep existing headers unchanged |
| Substantial contribution | Append your copyright line below existing lines |

Example of multi-author file:

```python
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-FileCopyrightText: 2026 Contributor Name <contributor@example.com>
# SPDX-License-Identifier: Apache-2.0
```

You retain copyright of your contribution. The Apache-2.0 license — including its
patent grant — applies automatically upon submission.

---

## 5. Third-Party Dependency Policy

Zenzic may only depend on libraries with Apache-2.0-compatible licenses:

| License | Compatible | Notes |
| :--- | :---: | :--- |
| MIT | ✅ | Permissive |
| BSD 2/3-Clause | ✅ | Permissive |
| Apache-2.0 | ✅ | Identical |
| LGPL-3.0 | ✅ | Library use only |
| ISC | ✅ | MIT-equivalent |
| GPL-2.0 / GPL-3.0 | ❌ | Copyleft contamination |
| Proprietary | ❌ | Not open-source |

For step-by-step instructions on adding dependencies, see [Release and Governance Protocol — Adding a Dependency](../../how-to/release-governance-protocol.md#adding-a-dependency).

---

## 6. Legal Disclaimer

This document provides operational guidance, not legal advice. For questions
regarding Apache-2.0 compliance, patent grants, or contribution rights in your
jurisdiction, consult qualified legal counsel.

**References:**

- Apache License 2.0
- REUSE 3.3 Specification
- SPDX License List
