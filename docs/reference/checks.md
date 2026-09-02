---
title: Checks Reference
description: Six independent checks for documentation integrity — from broken links to leaked credentials.
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

## Checks Reference {#checks-reference}

Zenzic runs **six independent checks**. Each addresses a distinct category of documentation rot — the slow degradation that happens when a project grows and documentation maintenance falls behind development.

| Check | CLI | What it catches |
| :--- | :--- | :--- |
| [Links](#check-links) | `zenzic check links` | Broken internal links, dead anchors, unreachable URLs |
| [Orphans](#check-orphans) | `zenzic check orphans` | `.md` files present on disk but absent from nav |
| [Snippets](#check-snippets) | `zenzic check snippets` | Python/YAML/JSON/TOML syntax errors in fenced blocks |
| [Placeholders](#check-placeholders) | `zenzic check placeholders` | Placeholder pages with low word count or patterns |
| [Assets](#check-assets) | `zenzic check assets` | Media never referenced by any page |
| [References](#check-references) | `zenzic check references` | Dangling ref-links, dead definitions, leaked credentials |

---

## Links {#check-links}

**CLI:** `zenzic check links [--strict]`

Link rot is one of the most common and most visible documentation failures. A developer renames a page, moves a section, or deletes an anchor, and the links that pointed to it silently become dead ends.

`zenzic check links` uses a native Python parser — no subprocesses, no build driver dependency. It scans every `.md` file under `docs/`, extracts all Markdown links with a fenced-block-aware state machine, and validates them in two tiers.

### Tier 1 — internal links (always checked)

Relative and site-absolute paths are resolved against the `docs/` directory in memory. The target file must exist in the scanned file set. Extension-less paths (`setup`) and directory-index paths (`setup/`) are also resolved. If the link includes a `#fragment`, Zenzic extracts heading anchors from the target file and verifies the fragment matches.

- `[text](missing-page.md)` → target file not found
- `[text](page.md#missing-anchor)` → anchor not found in target

All `.md` files are read once; anchors are pre-computed from headings (`# Heading` → `#heading`). No additional I/O per link.

### Tier 2 — external links (`--strict` only)

With `--strict`, every `http://` and `https://` URL in the docs is validated via concurrent HTTP HEAD requests using `httpx`. Up to 20 connections run simultaneously. Servers that reject HEAD receive a GET fallback. The same URL referenced in multiple pages is pinged exactly once.

Servers returning `401`, `403`, or `429` are treated as reachable — these indicate access restrictions, not broken links. Timeouts (>10 s) and connection errors are reported as failures.

### What is never validated

- Links inside fenced code blocks or inline code spans — the extractor skips them
- `mailto:`, `data:`, `ftp:`, `tel:` and similar non-HTTP schemes

!!! tip "Same-page anchor validation"

    Links like `[text](#section)` that point to a heading within the same file are always validated against `Z102` — there is no configuration flag to disable this check.

### Finding codes

| Code | Severity | Meaning |
| :--- | :---: | :--- |
| `Z101` | error | **Broken link** — target does not exist in the VSM |
| `Z103` | error | **Orphan link** — target exists on disk but not in site navigation |
| `Z105` | error | **Absolute path** — link uses a site-absolute path (`/docs/page`) instead of a relative path (`../page`) |

`Z101`, `Z103`, and `Z105` are all error-severity findings and block with exit code 1. `Z105` is error-severity because absolute paths break portability when a site is hosted in a subdirectory.

!!! note "Physical Consistency — why relative paths matter"

    Some build engines allow frontmatter `slug` overrides that decouple a page's URL from its filesystem location. When this happens, the "parent directory" for relative link resolution may differ between the build engine (which resolves from the URL) and Zenzic (which resolves from the file path).

    **Best practice:** keep the filesystem structure aligned with the URL structure. If you move a file to `guides/checks.md`, let its URL become `/docs/guides/checks` rather than forcing a slug back to `/docs/checks`. This guarantees that `../` links resolve identically for both the integrity engine and the build engine.

**Zenzic output — gutter reporter:**

### Path Traversal Guard -- system-path traversal {#path-traversal-guard}

The path traversal guard treats host-path traversal as a **security event**, not routine link hygiene. If a link escapes `docs/` and resolves to OS system paths (`/etc/`, `/root/`, `/var/`, `/proc/`, `/sys/`, `/usr/`), Zenzic emits `Z203 PATH_TRAVERSAL_FATAL` and exits with code **3**.

| Code | Severity | Exit code | Meaning |
| :--- | :---: | :---: | :--- |
| `Z203` (`PATH_TRAVERSAL_FATAL`) | security_incident | **3** | Href targets an OS system directory |
| `Z202` (`PATH_TRAVERSAL`) | error | 1 | Href escapes `docs/` to a non-system path |

!!! danger "Exit Code 3 — Path Traversal Guard"
    A `Z203 PATH_TRAVERSAL_FATAL` finding means a documentation source file contains a link whose resolved target points to `/etc/passwd`, `/root/`, or another OS system path. This can indicate a template injection, a compromised documentation toolchain, or an author mistake that reveals internal infrastructure details. Treat it as a build-blocking security incident.

---

## Orphans {#check-orphans}

**CLI:** `zenzic check orphans`

An orphan page exists on disk but is not listed in the site navigation. It is invisible to readers who follow the nav tree — it can only be reached by guessing the URL or finding a direct link.

**What it catches:**

- Pages created on disk but never added to `nav`
- Pages whose `nav` entry was removed without deleting the file

---

## Snippets {#check-snippets}

**CLI:** `zenzic check snippets`

Code examples in documentation are tested less rigorously than production code. A snippet that worked when it was written may have a syntax error introduced by a refactor, a copy-paste mistake, or a manual edit that was never reviewed.

### Supported languages

| Language tag | Parser | What is checked |
| :--- | :--- | :--- |
| `python`, `py` | `compile()` in `exec` mode | Python syntax |
| `yaml`, `yml` | `yaml.safe_load()` | YAML structure |
| `json` | `json.loads()` | JSON syntax |
| `toml` | `tomllib.loads()` | TOML syntax |

Blocks tagged with any other language (`bash`, `javascript`, `mermaid`, etc.) are treated as plain text and are not syntax-checked. However, **every fenced block is still scanned by the Zenzic credential scanner** for credential patterns.

### What it catches

- **Python:** `SyntaxError` — missing colons, unmatched brackets, invalid expressions
- **YAML:** structural errors — unclosed sequences, invalid mappings, duplicate keys
- **JSON:** `JSONDecodeError` — trailing commas, missing quotes, unmatched brackets
- **TOML:** `TOMLDecodeError` — missing quotes on values, invalid key syntax

!!! tip "Tuning"

    Use `snippet_min_lines` in `.zenzic.toml` to skip short blocks. The default of `1` checks everything. Set it to `3` or higher to ignore import stubs.

    ```toml
    # .zenzic.toml
    snippet_min_lines = 3
    ```

---

## Placeholders {#check-placeholders}

**CLI:** `zenzic check placeholders`

Placeholder pages are pages that were created as stubs and never completed. They are documentation debt.

### Signal 1 — word count

Pages with fewer than `placeholder_max_words` words (default: 50) are flagged as `short-content`.

### Signal 2 — pattern match

Lines containing any string from `placeholder_patterns` (case-insensitive) are flagged as `placeholder-text`. Default patterns include:

```text
coming soon
work in progress
wip
todo
to do
stub
placeholder
fixme
tbd
draft
da completare
in costruzione
bozza
prossimamente
```

Both signals are independent. A page may trigger one, both, or neither.

!!! tip "Tuning"

    ```toml
    # .zenzic.toml
    placeholder_max_words = 100
    placeholder_patterns = ["coming soon", "wip", "fixme", "tbd", "draft"]
    ```

---

## Assets {#check-assets}

**CLI:**

- `zenzic check assets` — Check for unused asset files
- `zenzic clean assets` — Safely remove unused assets

!!! note "Autofix available"
    Use `zenzic clean assets` to automatically delete any unused assets found by this check. Pass `-y` to skip confirmation, or `--dry-run` to preview. Zenzic will never delete files matching your `excluded_assets`, `excluded_dirs`, or `excluded_build_artifacts` patterns.

An asset is considered **used** if it appears as a Markdown image link (`![alt](path)`) or an HTML `<img src="...">` tag in any `.md` file. Paths are normalised using POSIX path arithmetic.

**Always excluded:** `.css`, `.js`, `.yml` files are never reported as unused — they are typically theme overrides or build configuration.

**What it catches:**

- Screenshots uploaded but never embedded
- Images left over after a page reorganisation
- Attachments linked from a page that no longer exists

---

## References {#check-references}

**CLI:** `zenzic check references`

The security and link-integrity check for [Markdown reference-style links](https://spec.commonmark.org/current/#link-reference-definitions). Also acts as the primary surface for the **credential scanner**.

### Reference finding codes

| Code | Severity | Exit code | Meaning |
| :--- | :---: | :---: | :--- |
| `DANGLING_REF` | error | 1 | `[text][id]` — `id` has no definition in the file |
| `DEAD_DEF` | warning | 0 / 1 `--strict` | `[id]: url` defined but never referenced |
| `DUPLICATE_DEF` | warning | 0 / 1 `--strict` | Same `id` defined twice; first wins |
| `MISSING_ALT` | warning | 0 / 1 `--strict` | Image with blank or absent alt text |
| credential scanner pattern match | security_breach | **2** | Credential detected in any line or URL |

### credential scanner — credential detection

The credential scanner scans **every line of every file** during Pass 1, including lines inside fenced code blocks.

**Detected pattern families:**

| Pattern | What it catches |
| :--- | :--- |
| `openai-api-key` | OpenAI API keys (`sk-…`) |
| `github-token` | GitHub personal / OAuth tokens (`gh[pousr]_…`) |
| `aws-access-key` | AWS IAM access key IDs (`AKIA…`) |
| `stripe-live-key` | Stripe live secret keys (`sk_live_…`) |
| `slack-token` | Slack bot / user / app tokens (`xox[baprs]-…`) |
| `google-api-key` | Google Cloud / Maps API keys (`AIza…`) |
| `private-key` | PEM private keys (`-----BEGIN … PRIVATE KEY-----`) |
| `hex-encoded-payload` | Hex-encoded byte sequences (3+ consecutive `\xNN` escapes) |
| `gitlab-pat` | GitLab Personal Access Tokens (`glpat-…`) |

**Exit Code 2** is reserved for credential scanner events. It is never suppressed by `--exit-zero` or `exit_zero = true` in `.zenzic.toml`.

!!! danger "If you receive exit code 2"

    Rotate the exposed credential immediately, then remove or replace the offending line. Do not commit the secret into repository history.

---

## See Also

- [Finding Codes Index](./finding-codes.md)
