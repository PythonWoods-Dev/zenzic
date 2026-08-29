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
- **Custom Rule SDK v3:** Authors implementing enterprise or domain-specific rules should subclass `ZenzicRuleV3` from `zenzic.sdk`. Custom rules must be deterministic, pure functions operating over AST or line streams with zero side effects.
- **Frozen Contract Awareness:** Do not alter immutable surfaces (`FROZEN_CODES`, `NON_SUPPRESSIBLE_CODES`, `PLUGIN_FORBIDDEN_EXITS`) without an explicit architecture decision record (ADR).
- **Inspect-First Workflow:** Treat `zenzic inspect codes` as the source of truth before editing examples, checks tables, or changelog narratives.

---

## Custom Rule SDK v3 (Enterprise Rule Development)

Zenzic provides the **Custom Rule SDK v3** (`zenzic.sdk`) allowing teams to author custom, typed Python lint rules that execute alongside the built-in analyzer.

> **v0.28.0 Architecture Shift:** The legacy un-typed `BaseASTRule` (v2 API) was removed in v0.28.0. All custom rules must now inherit from `ZenzicRuleV3` and declare a typed `RuleMetadata` schema.

### 1. Architecture & Base Contracts

Every SDK v3 rule inherits from `ZenzicRuleV3` (`from zenzic.sdk import ZenzicRuleV3, RuleMetadata`) and defines a `metadata` class attribute:

```python
from pydantic import BaseModel
from zenzic.models.rules import RuleMetadata, RuleSeverity, TaxonomyCategory
from zenzic.sdk import ZenzicRuleV3
```

#### The `RuleMetadata` Contract

| Field | Type | Description |
|:---|:---|:---|
| `code` | `str` | Unique rule identifier. Must start with `ZZ-` (e.g. `ZZ-REQ-FOOTER`) to avoid collision with core codes (ADR-012). |
| `title` | `str` | Short human-readable title. |
| `description` | `str` | Architectural description of the invariant being verified. |
| `severity` | `"error" \| "warning" \| "info"` | Finding severity level (default: `"warning"`). |
| `category` | `"structural" \| "navigation" \| "content" \| "brand" \| "governance"` | Taxonomy category for Documentation Quality Score (DQS) weighting. |
| `penalty` | `float` | DQS penalty points deducted per finding (default: `1.0`). |
| `docs_url` | `str \| None` | Optional URL pointing to the rule's reference documentation. |
| `supports_autofix` | `bool` | Flag indicating whether automated fixes are available. |

#### Visitor Hooks

Custom rules can override one or more specialized visitor hooks:

- **`visit_document(self, file_path: Path, text: str) -> list[RuleFinding]`**: Inspects full raw document content (e.g. frontmatter structure, whole-page invariants, mandatory headers/footers).
- **`visit_line(self, file_path: Path, line_no: int, line_text: str) -> list[RuleFinding]`**: Evaluates individual source lines in a single linear pass.
- **`visit_link(self, file_path: Path, line_no: int, link_text: str, target_url: str) -> list[RuleFinding]`**: Inspects Markdown and HTML link targets and anchors.
- **`visit_heading(self, file_path: Path, line_no: int, level: int, title: str) -> list[RuleFinding]`**: Validates heading level hierarchy and heading titles.
- **`visit_code_block(self, file_path: Path, start_line: int, lang: str, code: str) -> list[RuleFinding]`**: Inspects fenced code blocks, syntax tags, and snippets.

Findings are constructed via `self.create_finding(file_path=..., line_no=..., message=..., matched_line=..., match_text=...)`.

---

### 2. Complete Implementation Example

The following example implements an enterprise rule enforcing that all published documents conclude with a mandatory corporate copyright footer:

```python
# .zenzic/rules/mandatory_footer.py
from pathlib import Path
from zenzic.core.rules import RuleFinding
from zenzic.models.rules import RuleMetadata
from zenzic.sdk import ZenzicRuleV3


class MandatoryCorporateFooterRule(ZenzicRuleV3):
    """Enforces that all published documentation files contain the standard corporate footer."""

    metadata = RuleMetadata(
        code="ZZ-REQ-FOOTER",
        title="Mandatory Corporate Footer",
        description="Documentation pages must conclude with the standard corporate copyright footer.",
        severity="error",
        category="brand",
        penalty=2.0,
    )

    MANDATORY_FOOTER = "<!-- ACME Corp. All Rights Reserved -->"

    def visit_document(self, file_path: Path, text: str) -> list[RuleFinding]:
        if self.MANDATORY_FOOTER not in text:
            last_line_no = max(1, len(text.splitlines()))
            return [
                self.create_finding(
                    file_path=file_path,
                    line_no=last_line_no,
                    message="Missing required corporate footer marker.",
                    match_text=self.MANDATORY_FOOTER,
                )
            ]
        return []
```

---

### 3. Strict Determinism & Sandbox Constraints

To preserve mathematical determinism ($O(N)$ runtime complexity) and enforce the **Sovereign Sandbox (ADR-007)**, all custom rules MUST adhere to these non-negotiable invariants:

1. **Zero Network I/O (Forbidden: HTTP, HTTPS, DNS, Sockets)**:
   Rules must never initiate network connections. Network I/O violates offline verification guarantees and introduces non-deterministic latency.
2. **Zero Subprocesses (Forbidden: `subprocess`, `os.system`, `popen`)**:
   Subprocess execution is strictly forbidden. Zenzic operates under a pure zero-subprocess contract (ADR-002).
3. **No Probabilistic NLP or Heavy ML Models**:
   Rules must be deterministic mathematical functions. Using external LLM APIs, non-deterministic tokenizers, or stochastic models is prohibited.
4. **RE2 Regular Expression Discipline (ADR-013)**:
   Rules must never use the standard Python `re` module with backtracking or lookaround assertions. Use the linear-time `zenzic.core.regex` wrapper (`import zenzic.core.regex as re`) to guarantee immunity to Catastrophic Backtracking (ReDoS).
5. **Pure Functions & Immutability**:
   Rules must be side-effect-free: no filesystem mutations, no mutable module-level state, and no shared state across files.

---

### 4. Registering Custom Rules

Custom rules can be registered using either of two methods:

#### Method A: Project-Local Auto-Discovery (Recommended)

Place custom rule Python files inside the `.zenzic/rules/` directory at the repository root:

```text
my-project/
├── .zenzic/
│   └── rules/
│       ├── __init__.py
│       └── mandatory_footer.py
└── .zenzic.toml
```

Any class subclassing `ZenzicRuleV3` inside `.zenzic/rules/*.py` is automatically discovered, instantiated, and executed during `zenzic check all`.

#### Method B: Declarative Registration in `.zenzic.toml`

For installed Python packages or shared libraries, register the fully qualified class path under `[[custom_rules]]` in `.zenzic.toml`:

```toml
[[custom_rules]]
class_name = "my_enterprise_package.rules.MandatoryCorporateFooterRule"
```

For simple single-line regex rules without Python code:

```toml
[[custom_rules]]
id = "ZZ-NOCLICKHERE"
pattern = "(?i)\\bclick here\\b|\\bclicca qui\\b"
message = "Avoid generic link text. Use descriptive anchor text."
severity = "error"
```

For extended developer guides, see [Writing Custom Rules](docs/developers/how-to/write-ast-rule.md).

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
| Hero screenshot | `just screenshot-hero` | — | Run the "Power Triad" sandbox (`tests/sandboxes/hero_specimen/`) for a manual landing-page terminal screenshot — exits 3 by design, capture the output rather than treating it as a failure |
| Circular-link screenshot | `just screenshot-circular` | — | Run the circular-link sandbox (`tests/sandboxes/screenshot_circular/`) for a manual terminal screenshot demonstrating `Z106` `CIRCULAR_LINK` |

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
