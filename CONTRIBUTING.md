<!--
SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
SPDX-License-Identifier: Apache-2.0
-->

# Contributing to Zenzic Core

Thank you for your interest in contributing to Zenzic Core!

Zenzic is a Deterministic Document Integrity Engine for Markdown/MDX graphs.
We welcome contributions that improve reliability, performance, adapter accuracy, or usability of the Python Core engine and CLI.

## Multi-Repo Ecosystem Architecture

Zenzic is structured across three independent, dedicated repositories:

| Repository | Purpose | Primary Stack |
|:---|:---|:---|
| **[zenzic](https://github.com/PythonWoods/zenzic)** (this repo) | Python Core analysis engine & CLI (`src/zenzic`) | Python 3.10+, `uv`, `pytest`, `mypy` |
| **[zenzic-vscode](https://github.com/PythonWoods/zenzic-vscode)** | Official VS Code Extension (LSP Thin Client) | TypeScript, Node.js 24+, VS Code API |
| **[zenzic-action](https://github.com/PythonWoods/zenzic-action)** | Official GitHub Action CI/CD Wrapper | YAML, Bash, SARIF Upload |

**If you want to contribute to the core analysis engine** (new checks, adapters, bug fixes, CLI features, or performance improvements) — you are in the right place!

> **Brand System** — The visual identity and color palette reference live at
> <https://zenzic.dev/assets/brand/zenzic-brand-system.html>

---

## Contributor Contract & Code Governance

Before proposing rule or core engine changes, contributors must validate impact against the live code registry and tier ownership model:

- **Tier Ownership Model:** Findings are grouped into Core (Z1xx), Security (Z2xx), and Governance/Structure (Z3xx–Z6xx) domains. Keep changes in the correct band.
- **Custom Rule SDK v3:** Authors implementing enterprise or domain-specific rules should subclass `ZenzicRuleV3` from `zenzic.sdk.v3.rule`. Custom rules must be deterministic, pure functions operating over AST or line streams with zero side effects.
- **Frozen Contract Awareness:** Do not alter immutable surfaces (`FROZEN_CODES`, `NON_SUPPRESSIBLE_CODES`, `PLUGIN_FORBIDDEN_EXITS`) without an explicit architecture decision record (ADR).
- **Inspect-First Workflow:** Treat `zenzic inspect codes` as the source of truth before editing examples, checks tables, or changelog narratives.

---

## Enterprise Governance & Contribution Policy

To maintain security, architectural integrity, and legal compliance, all contributions must adhere to these guidelines:

1. **Issue-First Policy**: No Pull Request will be reviewed or merged unless it is preceded by an Issue formally discussed and approved by maintainers. Link the approved Issue in your PR description.
2. **Mandatory Cryptographic Commit Signatures**: Every commit must be cryptographically signed using GPG, SSH, or S/MIME keypairs (appearing as **Verified** on GitHub). Unsigned commits will be rejected by branch rulesets.
3. **No AI Slop Clause**: We enforce a strict policy against unverified AI-generated code. Contributors must fully understand, explain, and architecturally justify every single line of code proposed in a PR. Proposing code that you cannot explain will lead to immediate rejection.
4. **Developer Certificate of Origin (DCO)**: All commits must include a `Signed-off-by:` line (using `git commit -s`) certifying compliance with the DCO.
5. **Conventional Commits**: Commit messages must strictly follow the Conventional Commits specification (e.g., `feat(core): add block anchor support (#123)`).

---

## Prerequisites

| Requirement | Version | Notes |
|:---|:---|:---|
| **Python** | ≥ 3.10 | Core engine floor; validated on 3.10 & 3.14 in CI |
| **uv** | required | Package manager — `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **just** | required | Task runner — `cargo install just` or via OS package manager |

---

## First-Time Setup

```bash
git clone git@github.com:PythonWoods/zenzic.git
cd zenzic
just sync
```

`just sync` installs all dependency groups via `uv sync --all-groups`.

Install pre-commit and pre-push hooks immediately after sync (mandatory):

```bash
uv run --active pre-commit install              # commit-stage: light hooks (ruff, format, hygiene, guard)
uv run --active pre-commit install -t pre-push  # push-stage: Final Guard (just verify before pushing)
```

Configure SSH commit signing (required — all commits must appear **Verified** on GitHub):

```bash
# One-time global setup (skip if already configured)
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub   # adjust path if different
git config --global commit.gpgsign true
```

Register your public key as a **Signing Key** at <https://github.com/settings/ssh>.

Run the full verification gate before pushing:

```bash
just verify
```

`just verify` is the canonical entry point: pre-commit on all files → `pytest tests/` → `zenzic check all --strict` → `zenzic score --stamp` → `zenzic score --check-stamp`.

---

## The 4-Lifecycle-Gates Model

| Stage | Trigger | What runs | Speed |
|:---|:---|:---|:---|
| **TDD inner loop** | `just test` | `pytest -n auto` (parallel, no coverage) | ⚡ instant |
| **Commit** | `git commit` | Light hooks (ruff, format, file hygiene) | < 5 s |
| **Final Guard** | `just verify` (manual/CI) | pre-commit → `pytest tests/` → `zenzic check all --strict` → `zenzic score --stamp` → `zenzic score --check-stamp` | < 60 s |
| **CI** | GitHub Actions | `just verify` (identical) | matches local |

---

## Running Tasks

| Task | `just` command | `nox` equivalent | Description |
|:---|:---|:---|:---|
| Bootstrap | `just sync` | — | Install / update all dependency groups |
| **Self-lint** | **`just check`** | — | **Run Zenzic on its own codebase (strict)** |
| Test (fast) | `just test` | — | pytest `-n auto`, no coverage (TDD inner loop) |
| Test (audit) | `just test-cov` | `nox -s tests` | pytest serial + branch coverage JSON |
| Test (thorough) | `just test-full` | — | pytest with Hypothesis **ci** profile (500 examples) |
| **Final Guard** | **`just verify`** | — | **Full pre-push quality gate** |
| Show version | `just version` | — | Print current version from bump-my-version |
| Clean | `just clean` | — | Remove `dist/`, `.hypothesis/`, caches |

---

## Cross-Platform Compatibility

When working with file paths in any contribution, use `pathlib.Path` throughout — never string concatenation or `os.sep`:

- `Path("a") / "b"` — always, never `"a" + os.sep + "b"` or `"a/b"` as string literal.
- Use `.as_posix()` only at the point of comparison against URLs or POSIX-style config values.
- Test fixtures that construct paths must use `tmp_path / "subdir"`, not `"/tmp/subdir"`.

---

## 📖 Documentation & Support

| Area | URL | Audience |
|:---|:---|:---|
| 👤 User Guide | [zenzic.dev](https://zenzic.dev/) | Install, configure, CI/CD, finding codes |
| 🔧 Developer Portal | [zenzic.dev/developers](https://zenzic.dev/developers/) | Adapters, ADRs, CLI architecture |
| 🛡️ Security | [SECURITY.md](SECURITY.md) | Security reviewer |

---

## 📄 License

Apache-2.0 — see [LICENSE](LICENSE). This project strictly adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
