<!--
SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
SPDX-License-Identifier: Apache-2.0
-->

# Security Policy

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

If you discover a security vulnerability in Zenzic — including issues with the credential
scanner, the path traversal protection, or any other part of the Core —
report it privately via one of these channels:

- **GitHub Security Advisories** (preferred): [github.com/PythonWoods/zenzic/security/advisories](https://github.com/PythonWoods/zenzic/security/advisories)
- **Email**: `dev@pythonwoods.dev` — subject line: `[SECURITY] Zenzic — <brief description>`

For lower-severity, non-exploitable issues (Shield false positives/negatives, incorrect
exit-code behaviour, or a suspected ReDoS in a specific input) that don't expose secrets or
enable remote code execution, a public
[Security Vulnerability issue template](https://github.com/PythonWoods/zenzic/issues/new?template=security_vulnerability.yml)
is also available — it never asks for real secret values.

Please include a clear description of the vulnerability, steps to reproduce, potential
impact, and a suggested fix if available.

We will acknowledge your report within **72 hours** and aim to release a patch within
**14 days** of confirming the issue.

## Scope

The following areas are in-scope for security reports:

| Area | Description |
| :--- | :---------- |
| **Scanner bypass** | A credential pattern that passes undetected through the nine-family credential scanner |
| **Path traversal bypass** | A crafted link that escapes the `docs/` root without triggering the path traversal guard |
| **Dependency CVE** | A known CVE in a runtime dependency (`typer`, `rich`, `pyyaml`, `pydantic`, `httpx`) |
| **Code execution** | A crafted Markdown or config file that causes arbitrary code execution during linting |
| **Exit code suppression** | Any method that prevents exit code `2` from being emitted on a credential scanner finding |

Out-of-scope: documentation content errors, cosmetic output formatting, or issues that
only affect `nox` development sessions (not the published `zenzic` package).

## Security design notes

Zenzic v0.4.0+ has **no subprocess calls** in the linting path. The tool reads raw source
files and performs all analysis in pure Python. It does not execute `mkdocs build` or any
other build tool during `check`, `score`, or `diff`. The attack surface is limited to:

- **Crafted Markdown files** — Zenzic parses Markdown with a pure state-machine; the path
  traversal guard rejects any href that resolves outside `docs/`.
- **Crafted config files** — `zenzic.toml`, `mkdocs.yml`, and `zensical.toml` are parsed
  as plain data (TOML/YAML). No code is evaluated. Custom rules (`[[custom_rules]]`) are
  plain regex patterns compiled once at load time.
- **Dependencies** — run `nox -s security` (pip-audit) regularly to detect known CVEs in
  the dependency tree.

## Supply-chain assurance (SLSA-aligned)

Zenzic distribution workflows enforce a SLSA-aligned integrity baseline for
build and release operations:

- GitHub Actions in release-critical workflows are pinned to immutable commit SHAs.
- Dependency synchronization uses `uv.lock` with frozen resolution (`uv sync --frozen`).
- Release artifacts are produced with build provenance attestations.

This model provides deterministic builds and verifiable provenance for published
release assets.

### Provenance verification for end users

End users can verify provenance for downloaded release artifacts with GitHub
Artifact Attestations.

1. Download the artifact from the release page (for example, `*.whl` or `*.tar.gz`).
1. Verify the attestation against the repository:

```bash
gh attestation verify ./zenzic-<version>-py3-none-any.whl --repo PythonWoods/zenzic
```

1. Accept the artifact only when attestation verification succeeds.

## Supported versions

Zenzic follows a **single-track release model** — there is no maintained backport branch for
older minor versions. Only the current release on PyPI receives security fixes.

| Version | Support status |
| :------ | :------------- |
| `0.30.x` (current) | ✅ All security fixes |
| `< 0.30` | ❌ Unsupported — upgrade to the current release |

## Disclosure policy

We follow a **coordinated disclosure** model. We ask that you allow up to 14 days for a
patch to be released before any public disclosure. Confirmed reporters will be credited in
the release changelog unless they prefer to remain anonymous.
