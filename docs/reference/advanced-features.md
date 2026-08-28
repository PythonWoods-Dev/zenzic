---
description: "Reference integrity, credential scanner detection, and programmatic usage."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Advanced Features

Deep reference for the Three-Pass Pipeline, credential scanner, accessibility checks, and
programmatic usage from Python.

---

## Reference integrity {#reference-integrity-v020}

`zenzic check references` runs the **Three-Pass Reference Pipeline** — the core engine behind
every reference-quality and security check Zenzic performs.

### Why three passes

Markdown [reference-style links][syntax] separate *where a link points* (the definition) from
*where it appears* (the usage). A single-pass scanner cannot resolve a reference that appears
before its definition. Zenzic solves this with a deliberate three-pass structure:

| Pass | Name | What happens |
| :---: | :--- | :--- |
| 1 | **Harvest** | Stream the file line-by-line; record all `[id]: url` definitions into a `ReferenceMap`; run the credential scanner on every URL and line |
| 2 | **Cross-Check** | Re-stream the file; for every `[text][id]` usage, look up `id` in the now-complete `ReferenceMap`; flag missing IDs as **Dangling References** |
| 3 | **Integrity Report** | Compute the integrity score; append **Dead Definitions**, duplicate-ID warnings, and alt-text warnings to the findings list |

Pass 2 only begins when Pass 1 completes without security findings. If the credential scanner fires during
harvesting, Zenzic exits immediately with code 2 — no reference resolution occurs on files that
contain leaked credentials.

### What the pipeline catches

| Issue | Type | Blocks exit? |
| :--- | :---: | :---: |
| **Dangling Reference** — `[text][id]` where `id` has no definition | error | Yes |
| **Dead Definition** — `[id]: url` defined but never used by any link | warning | No (yes with `--strict`) |
| **Duplicate Definition** — same `id` defined twice; first wins (CommonMark §4.7) | warning | No |
| **Missing alt-text** — `![](url)` or `<img>` with blank/absent alt | warning | No |
| **Secret detected** — credential pattern found in a reference URL or line | security | **Exit 2** |
| **Path traversal** — link resolves to an OS system directory | security | **Exit 3** |

### Reference Integrity Score

Each file receives a per-file score:

```text
Reference Integrity = (resolved definitions / total definitions) × 100
```

A file where every defined reference is used at least once scores 100. Unused (dead) definitions
pull the score down. When a file has no definitions at all, the score is 100 by convention.

The integrity score is a **per-file diagnostic** — it does not feed into the `zenzic score`
overall quality score. Use it to identify files that accumulate unused reference link
boilerplate.

---

## credential scanner

The credential scanner runs **inside Pass 1** — every URL extracted from a reference definition is scanned
the moment the harvester encounters it, before any other processing continues. The credential scanner also
applies a defence-in-depth pass to non-definition lines to catch secrets in plain prose.

### Detected credential patterns

| Pattern name | Regex | What it catches |
| :--- | :--- | :--- |
| `openai-api-key` | `sk-[a-zA-Z0-9]{48}` | OpenAI API keys |
| `github-token` | `(?i)\b(?:ghp\|gho\|ghu\|ghs\|ghr)_[a-zA-Z0-9_.-]+\b` | GitHub personal, OAuth, app, and refresh tokens |
| `gitlab-pat` | `glpat-[A-Za-z0-9\-_]{20,}` | GitLab personal access tokens |
| `aws-access-key` | `AKIA[0-9A-Z]{16}` | AWS IAM access key IDs |
| `stripe-live-key` | `sk_live_[0-9a-zA-Z]{24}` | Stripe live secret keys |
| `slack-token` | `xox[baprs]-[0-9a-zA-Z]{10,48}` | Slack bot/user/app tokens |
| `google-api-key` | `AIza[0-9A-Za-z\-_]{35}` | Google Cloud / Maps API keys |
| `private-key` | `-----BEGIN [A-Z ]+ PRIVATE KEY-----` | PEM private keys (RSA, EC, etc.) |
| `hex-encoded-payload` | `(?:\x[0-9a-fA-F]{2}){3,}` | Detects obfuscation attempts that hide payloads or credentials via hex escapes. This technique is commonly used to evade naive string matchers and is treated as a critical source-transparency violation. |

### credential scanner behaviour {#credential-scanner-behaviour}

- **Every line is scanned** — including lines inside fenced code blocks (labelled or unlabelled).

  A credential committed in a `bash` example is still a committed credential.

- Detection is **non-suppressible** — `--exit-zero`, `exit_zero = true` in `.zenzic.toml`, and

  `--strict` have no effect on credential scanner findings.

- Exit code 2 is reserved **exclusively** for credential scanner events. It is never used for ordinary check

  failures.

- Exit code 3 is reserved for **path traversal guard** events — links that resolve to OS system

  directories. Like exit code 2, it is never suppressed.

- Files with security findings are **excluded from link validation** — Zenzic does not ping URLs

  that may contain leaked credentials.

- **Code block link isolation** — while the credential scanner scans inside fenced blocks, the link and

  reference validators do not. Example URLs inside code blocks (e.g. `https://api.example.com`)
  never produce false-positive link errors.

!!! danger "If you receive exit code 2"
    Treat it as a build-blocking security incident. Rotate the exposed credential immediately,
    then remove or replace the offending reference URL. Do not commit the secret into history.

!!! note "See the credential scanner in action"
    The repository ships `examples/safety_demonstration.md` — an intentional test fixture
    containing a circular link and a hex-encoded payload. Run `zenzic check all` against it
    to observe a live credential scanner finding and a `CIRCULAR_LINK` info finding.

---

## Hybrid scanning logic

Zenzic applies different scanning rules to prose and code blocks because the two contexts have
different risk profiles:

| Content location | credential scanner (secrets) | Snippet syntax | Link / ref validation |
| :--- | :---: | :---: | :---: |
| Prose and reference definitions | ✓ | — | ✓ |
| Fenced block — supported language (`python`, `yaml`, `json`, `toml`) | ✓ | ✓ | — |
| Fenced block — unsupported language (`bash`, `javascript`, …) | ✓ | — | — |
| Fenced block — unlabelled (` ``` `) | ✓ | — | — |

**Why links are excluded from fenced blocks:** documentation examples routinely contain
illustrative URLs (`https://api.example.com/v1/users`) that do not exist as real endpoints.
Checking them would produce hundreds of false positives with no security value.

**Why secrets are included everywhere:** a credential embedded in a `bash` example is still
a committed secret. It lives in git history, is indexed by code-search tools, and can be
extracted by automated scanners that do not respect Markdown formatting.

**Why syntax checking is limited to known parsers:** validating Bash or JavaScript would
require third-party parsers or subprocesses, violating the No-Subprocess Pillar. Zenzic
validates what it can validate purely in Python.

---

## Alt-text accessibility

`zenzic check references` also flags images that lack meaningful alt text:

- **Markdown inline images** — `![](url)` or `![   ](url)` (blank alt string)
- **HTML `<img>` tags** — `<img src="...">` with no `alt` attribute, or `alt=""` with no

  content

An explicitly empty `alt=""` is treated as intentionally decorative and is **not** flagged.
A completely absent `alt` attribute, or whitespace-only alt text, is flagged as a warning.

Alt-text findings are warnings — they appear in the report but do not affect the exit code
unless `--strict` is active.

---

## Programmatic usage

Import Zenzic's scanner functions directly into your own Python tooling.

### Single-file scan

Use `ReferenceScanner` to run the three-pass pipeline on one file:

```python
from pathlib import Path
from zenzic.core.scanner import ReferenceScanner

scanner = ReferenceScanner(Path("docs/guide.md"))

# Pass 1 — harvest definitions; collect credential scanner findings
security_findings = []
for lineno, event_type, data in scanner.harvest():
    if event_type == "SECRET":
        security_findings.append(data)
        # In production: raise SystemExit(2) or typer.Exit(2) here

# Pass 2 — resolve reference links (must be after harvest)
cross_check_findings = scanner.cross_check()

# Pass 3 — compute integrity score and consolidate all findings
report = scanner.get_integrity_report(cross_check_findings, security_findings)

print(f"Integrity score: {report.score:.1f}")
for f in report.findings:
    level = "WARN" if f.is_warning else "ERROR"
    print(f"  [{level}] {f.file_path}:{f.line_no} — {f.detail}")
```

### Multi-file scan

Use `scan_docs_references` to scan every `.md` file in a repository and optionally
validate external URLs:

```python
from pathlib import Path
from zenzic.core.scanner import scan_docs_references
from zenzic.core.exclusion import LayeredExclusionManager
from zenzic.models.config import ZenzicConfig

config, _ = ZenzicConfig.load(Path("."))
exclusion_mgr = LayeredExclusionManager(config)

reports, link_errors = scan_docs_references(
    Path("."),
    exclusion_mgr,
    config=config,
    validate_links=True,  # set False to skip HTTP validation
)

for report in reports:
    if report.security_findings:
        raise SystemExit(2)  # your code is responsible for exit-code enforcement
    for finding in report.findings:
        print(finding)

for error in link_errors:
    print(f"[LINK] {error}")
```

`scan_docs_references` deduplicates external URLs across the entire docs tree before
firing HTTP requests — 50 files linking to the same URL result in exactly one HEAD request.

### Hybrid Adaptive Engine

`scan_docs_references` is the single unified entry point for all scan modes.
It selects sequential or parallel execution **automatically** based on the
number of files in the repository:

| Repo size | Engine behaviour | Reason |
| :--- | :--- | :--- |
| < 1000 files | Sequential (always) | Process-spawn overhead (~200–400 ms) exceeds the parallelism benefit |
| ≥ 1000 files, `workers=1` | Sequential | Explicit serial override |
| ≥ 1000 files, `workers=None` or `workers=N` | Parallel (`ProcessPoolExecutor`) | CPU-bound regex work dominates; linear scaling |
| 5 000+ files | Parallel with `workers=cpu_count` | Proven 3–6× speedup on 8-core runners |

The `ADAPTIVE_PARALLEL_THRESHOLD` (1000 files) is the conservative
break-even point where parallelism pays for its own startup cost.

```python
from pathlib import Path
from zenzic.core.scanner import scan_docs_references
from zenzic.core.exclusion import LayeredExclusionManager
from zenzic.models.config import ZenzicConfig

config, _ = ZenzicConfig.load(Path("."))
exclusion_mgr = LayeredExclusionManager(config)

# Default: sequential (workers=1, zero overhead)
reports, _ = scan_docs_references(Path("."), exclusion_mgr, config=config)

# Explicit parallel: 4 workers, auto-activates only if ≥ 1000 files
reports, _ = scan_docs_references(Path("."), exclusion_mgr, config=config, workers=4)

# Fully automatic: ProcessPoolExecutor picks worker count from os.cpu_count()
reports, _ = scan_docs_references(Path("."), exclusion_mgr, config=config, workers=None)

# With external link validation (works in both sequential and parallel mode)
reports, link_errors = scan_docs_references(
    Path("."), exclusion_mgr, config=config, validate_links=True, workers=None
)
```

**Determinism guarantee:** results are always sorted by `file_path` regardless
of execution mode.  The same input always produces the same ordered output.

**Pickling contract for plugin rules (`BaseRule` subclasses):**

Rules are validated for pickle-serializability at engine construction time
(**eager validation**).  A non-serialisable rule raises `PluginContractError`
immediately — before any file is scanned.

- **Rules must be defined at module level.**  A class defined inside a function

  or lambda cannot be pickled and will be rejected at load time.

- **All instance attributes must be pickleable.**  Pre-compiled `re.compile()`

  patterns, strings, and numbers are always safe.  File handles, database
  connections, and lambda closures are not.

- **No mutable global state.**  Workers receive independent copies of the rule

  engine (via pickle).  A global counter mutated inside `check()` will be
  local to each worker process and discarded on completion — results will differ
  from sequential mode silently.  Return all state as `RuleFinding` objects.

See [Writing Plugin Rules](../developers/how-to/write-plugin.md) for the complete contract,
examples, and packaging instructions.

---

## Fenced-code and frontmatter exclusion

The harvester and cross-checker both skip content that should never trigger findings:

- **YAML frontmatter** — the leading `---` block (first line only) is skipped in its entirety,

  including any reference-like syntax it might contain.

- **Fenced code blocks** — lines inside ` ``` ` or `~~~` fences are ignored. URLs in code

  examples never produce false positives.

This exclusion is applied consistently in both Pass 1 and Pass 2.

---

## Nav-Aware Linking

Zenzic does not only check whether a linked file exists on disk — it checks whether that
file is **reachable** through the site navigation.  This catches an entire class of
navigation defects that file-existence checks miss entirely.

### Dark pages

A **dark page** is a file that exists on disk and is physically served by the engine at
its URL — but is missing from the site navigation.  The link works.  The page loads.
The user who follows it arrives successfully.  And then they are lost: no breadcrumb,
no menu entry, no way back through the navigation tree.

Dark pages are invisible to users browsing your site.  They are the documentation
equivalent of a room with no door — the room exists, but no one can find it without
already knowing where it is.

Zenzic flags links to dark pages as `UNREACHABLE_LINK`.  This is not a broken link.
It is a **navigation defect**: the link is syntactically correct, the file resolves,
but the destination is unreachable through normal browsing.

### How it works

When a build-engine config (`mkdocs.yml`) is present, Zenzic constructs a **Virtual Site
Map (VSM)** before running link validation.  The VSM maps every `.md` source file to:

- its **canonical URL** (e.g. `docs/guide/installation.md` → `/guide/installation/`)
- its **routing status** — one of `REACHABLE`, `ORPHAN_BUT_EXISTING`, `IGNORED`, or

  `CONFLICT`

A file is `REACHABLE` if it appears in the `nav:` section of `mkdocs.yml`.  A file is
`ORPHAN_BUT_EXISTING` if it lives on disk but has no nav entry — the engine copies it to
`site/` and serves it, but no user can find it through navigation.

### UNREACHABLE_LINK

When a link resolves to a dark page (`ORPHAN_BUT_EXISTING` or `IGNORED`) in the VSM,
Zenzic emits:

```text
  [UNREACHABLE_LINK] index.md:22 — 'guide/secret.md' resolves to '/guide/secret/'
  which exists on disk but is not listed in the site navigation (UNREACHABLE_LINK)
  — add it to nav in mkdocs.yml or remove the link
    │ - [Secret page](guide/secret.md)
```

The Visual Snippet (`│`) shows the exact source line so you can locate and fix the link
without searching through the file.

### Routing collision (CONFLICT)

Two source files that map to the same canonical URL produce a `CONFLICT` in the VSM.
The most common case is the **Double Index**: `index.md` and `README.md` coexisting in
the same directory.  Both produce the same URL (`/dir/`) — the build engine's behaviour
is undefined.  Zenzic detects this before the build runs.

### Engine behaviour

| Adapter | UNREACHABLE_LINK? | Trigger |
| :--- | :---: | :--- |
| **MkDocs** (with `mkdocs.yml` + `nav:`) | Yes | File not listed in `nav:` (`ORPHAN_BUT_EXISTING`) |
| **MkDocs** (no `nav:` declared) | No | All files auto-included by MkDocs |
| **Zensical** | Yes | File or directory starting with `_` (`IGNORED`) |
| **Standalone** (no engine config) | No | No routing concept |

!!! note "Fix an UNREACHABLE_LINK"
    Either add the target page to `nav:` in `mkdocs.yml`, or replace the link with one
    pointing to a reachable page.

### Private pages (Zensical) {#private-pages-zensical}

Files and directories whose name starts with an underscore (`_`) are treated as **private**
by Zenzic when the Zensical engine is active.  Links to these resources are flagged as
`UNREACHABLE_LINK` because Zensical never serves `_`-prefixed paths to the public.

```text
docs/
├── index.md
├── features.md
└── _private/           ← Zenzic's ZensicalAdapter ignores this directory entirely
    └── notes.md        ← links to this file → UNREACHABLE_LINK
```

```text
[UNREACHABLE_LINK] index.md:8 — '_private/notes.md' resolves to '/_private/notes/'
which exists on disk but is not listed in the site navigation (UNREACHABLE_LINK) —
add it to nav in mkdocs.yml or remove the link
  │ - [Private Notes](_private/notes.md)
```

This rule applies to any path segment starting with `_`:

| Path | Status |
| :--- | :--- |
| `_private/notes.md` | `IGNORED` → `UNREACHABLE_LINK` |
| `_drafts/test.md` | `IGNORED` → `UNREACHABLE_LINK` |
| `public/page.md` | `REACHABLE` — served normally |

!!! note "This is Zenzic's own convention, not a Zensical platform feature"
    Neither MkDocs nor Zensical itself treats underscore-prefixed directories as private —
    verified against Zensical's own official documentation, which describes no such
    convention. This is a modeling choice Zenzic's `ZensicalAdapter` applies internally
    (`_zensical.py`) when the Zensical engine is active; MkDocs-engine and Standalone-engine
    projects are unaffected. When switching engines, audit any `_`-prefixed
    directories in your docs tree.

---

## Multi-language documentation

When your project uses [MkDocs i18n](https://github.com/ultrabug/mkdocs-static-i18n) or
Zensical's locale system, Zenzic adapts automatically:

- **Locale directories suppressed from orphan detection** — files under `docs/it/`, `docs/fr/`,

  etc. are not reported as orphans. The adapter detects locale directories from the engine's
  i18n configuration.

- **Cross-locale link resolution** — the engine adapters resolve links that cross

  locale boundaries (e.g. a link from `docs/it/page.md` to `docs/en/page.md`) without false
  positives.

- **Standalone mode skips orphan check entirely** — when no build-engine config is present, every

  file would appear as an orphan. Zenzic skips the check rather than report noise.

!!! tip "Force Standalone mode to suppress orphan check"

    ```bash
    zenzic check all --engine standalone
    ```

---

---

## Policy-as-Code Engine

The **Policy-as-Code Engine** allows declarative enforcement of frontmatter schemas (e.g. `Z612`, `Z613`) and cross-namespace link boundaries (e.g. `Z614`, `Z615`, `Z616`) via the `[policies]` table in `.zenzic.toml`.

### Supported Policy Controls

| Policy Key | Target Code | Description |
| :--- | :---: | :--- |
| `required_frontmatter_keys` | `Z610` | Frontmatter keys that must be present in every Markdown file. |
| `forbidden_external_domains` | `Z611` | Domain names forbidden in external HTTP/HTTPS links. |
| `forbidden_frontmatter_keys` | `Z612` | Frontmatter keys prohibited from documentation files. |
| `frontmatter_schema_match` | `Z613` | Key-value pairs mapping frontmatter keys to RE2 regex patterns. |
| `allowed_external_domains` | `Z614` | Explicit allowlist for external links (blocks unapproved domains). |
| `required_url_schemes` | `Z615` | Approved URL schemes (`https`, `mailto`). |
| `cross_namespace_restrictions` | `Z616` | Zero-Trust link rules restricting cross-namespace linking. |

### Configuration Example

```toml title=".zenzic.toml"
[policies]
required_frontmatter_keys = ["title", "description"]
forbidden_external_domains = ["untrusted-domain.com"]
forbidden_frontmatter_keys = ["draft", "internal_notes"]

[policies.frontmatter_schema_match]
author = "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$"
```

---

## Custom Rule SDK v3

The **Custom Rule SDK v3** (`ZenzicRuleV3` + `RuleMetadata`) provides a typed framework for authoring custom analysis rules in Python.

!!! warning "v0.28.0 Removal of Custom Rules API v2"
    The legacy Custom Rules API v2 (`BaseASTRule`) was **hard-deprecated and removed in v0.28.0**. All custom rules must inherit from `ZenzicRuleV3` and provide a typed `RuleMetadata` instance to enforce severity, category, and DQS penalty.

### The `RuleMetadata` Instance

```python
from pathlib import Path
from zenzic.sdk import ZenzicRuleV3, RuleMetadata
from zenzic.core.rules import RuleFinding


class ForbiddenInternalUrlRule(ZenzicRuleV3):
    metadata = RuleMetadata(
        code="ZZ-NO-BAD-URL",
        title="Forbidden Internal URL",
        description="Internal staging URLs must not appear in published documentation.",
        severity="warning",
        category="content",
        penalty=1.0,
        supports_autofix=False,
    )

    def visit_line(self, file_path: Path, line_no: int, line_text: str) -> list[RuleFinding]:
        if "staging.internal" in line_text:
            return [
                self.create_finding(
                    file_path=file_path,
                    line_no=line_no,
                    message="Forbidden internal staging URL found.",
                    matched_line=line_text,
                )
            ]
        return []
```

### Discovery & Registration

Custom rules placed in `.zenzic/rules/*.py` are auto-discovered at scan startup. Alternatively, external rules can be registered via `[[custom_rules]]` in `.zenzic.toml`:

```toml title=".zenzic.toml"
[[custom_rules]]
class_name = "my_company.rules.ForbiddenInternalUrlRule"
```

[syntax]: https://spec.commonmark.org/0.31.2/#link-reference-definitions
