---
sidebar_position: 11
description: Rigorous definitions for every term used in the Zenzic documentation and CLI output.
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Glossary

This glossary provides precise definitions for all domain-specific terms used in Zenzic's documentation, CLI output, and source code. Terms are listed alphabetically.

---

## Terms

Glossary of key technical and domain concepts in alphabetical order.

### Adapter {#adapter}

A build-engine-specific module that implements the `BaseAdapter` protocol. Adapters translate between a documentation engine's file conventions (nav structure, locale directories, URL mapping) and Zenzic's engine-agnostic core. Built-in adapters: `MkDocsAdapter`, `ZensicalAdapter`, `StandaloneAdapter`. Third-party adapters can be registered via the `zenzic.adapters` entry-point group.

See: [Architecture -- Adapter Protocol](../explanation/architecture#adapter-protocol)

---

### Path Traversal Guard

A security classification applied when a documentation link resolves to an OS system directory (`/etc/`, `/root/`, `/var/`, `/proc/`, `/sys/`, `/usr/`). The path traversal guard fires the `PATH_TRAVERSAL_SUSPICIOUS` finding and forces **exit code 3** -- the highest-priority exit code in Zenzic. It also activates when `docs_dir` itself escapes the repository root (F4-1 jailbreak protection).

Path traversal guard events are never suppressed by `--exit-zero`. They indicate potential template injection, a compromised documentation toolchain, or unintentional infrastructure disclosure.

See: [Checks Reference -- Path Traversal Guard](./checks#path-traversal-guard)

---

### Dark Page {#dark-page}

A documentation page that exists on disk and is listed in the site navigation, but cannot be reached by following links from any other page. Dark Pages are structurally valid but functionally invisible -- readers can only find them by browsing the nav tree or guessing the URL directly. Distinct from Ghost Routes (not in nav at all) and orphans (on disk but not in nav).

---

### Ghost Route {#ghost-route}

A URL path that the build engine's nav configuration declares but that has no corresponding source file on disk. Ghost Routes represent entries that a reader would see in the navigation but that would result in a 404 when clicked. They are detected during VSM construction by comparing nav-declared paths against the physical file set.

---

### Hex Pattern Detector

The credential scanner pattern that detects hex-encoded byte sequences -- three or more consecutive `\xNN` escape sequences (e.g. `\x40\x41` · `\x42`, three in sequence). This pattern catches obfuscated payloads, shellcode fragments, or encoded credentials that appear in documentation examples. Part of the eight pattern families scanned by the Zenzic credential scanner.

---

### Layered Exclusion {#layered-exclusion}

The 4-level hierarchy that determines which files and directories Zenzic scans. Each level has a distinct role and precedence:

| Level | Name | Description |
| :---: | :--- | :--- |
| L1 | System Guardrails | Hardcoded immutable exclusions (`.git`, `.venv`, `node_modules`, etc.) |
| L2 | Forced Inclusions + VCS | Config `included_dirs`/`included_file_patterns` and `.gitignore` patterns |
| L3 | Config Exclusions | `excluded_dirs` and `excluded_file_patterns` from `.zenzic.toml` or `[tool.zenzic]` in `pyproject.toml` |
| L4 | CLI Overrides | `--exclude-dir` and `--include-dir` flags |

The hierarchy is evaluated top-to-bottom; the first matching rule wins. System Guardrails (L1) can never be overridden.

See: [Discovery & Exclusion](../explanation/discovery)

---

### Exclusion Zone {#privacy-gate}

The strict boundary within Zenzic's file discovery model where scanners are intentionally inhibited. Every inclusion and exclusion within the zone is traceable to a specific configuration line (`.zenzic.toml`) or CLI flag. Governed by the Layered Exclusion hierarchy.

---

### Reference Map {#reference-map}

A per-file data structure populated during Pass 1 of the Two-Pass Pipeline. The Reference Map stores all `[id]: url` reference definitions found in a Markdown file, keyed by normalised (lowercase, trimmed) ID. It tracks:

- **Definitions** -- `{norm_id: (url, line_no)}`, first-definition-wins per CommonMark 4.7.
- **Used IDs** -- set of IDs that were referenced via `[text][id]` or `[text]` shortcut syntax.
- **Duplicate IDs** -- set of IDs that were defined more than once.
- **Orphan definitions** -- definitions that were never referenced (dead definitions).
- **Integrity score** -- computed from the ratio of used definitions to total definitions.

---

### Zenzic Score {#zenzic-score}

A 0--100 quality score computed across four weighted categories: Structural (30%), Navigation (25%), Content (20%), and Brand & Assets (25%). Each category accumulates per-code penalty deductions (D092 — Zenzic Penalty Scorer). The score is computed by `zenzic score` and can be gated in CI via `fail_under` in `.zenzic.toml` or `--fail-under` on the CLI.

Use `zenzic score --save` to snapshot the current score and `zenzic diff` to compare against the baseline.

---

### Credential Scanner Violation

An exception raised by the credential scanner's IO Middleware (`safe_read_line`) when a credential is detected during metadata extraction. `ShieldViolation` is intentionally fatal -- it prevents the secret from entering any parser (YAML, Markdown, regex) by halting processing immediately. The caller must catch it and exit with **code 2**.

Distinct from a credential scanner *finding* (a `SecurityFinding` dataclass yielded during Pass 1 harvesting). A finding is data; a violation is a control-flow interruption.

---

### System Guardrails (L1) {#system-guardrails}

The immutable set of directories that Zenzic always excludes, regardless of any configuration or CLI flag. They are defined in `SYSTEM_EXCLUDED_DIRS` as a `frozenset`:

```text
.git          .github       .venv         node_modules
.nox          .tox          .pytest_cache .mypy_cache
.ruff_cache   __pycache__   .cache
.hypothesis   .temp
```

System Guardrails form Level 1 of the Layered Exclusion hierarchy. They cannot be removed by `included_dirs`, `--include-dir`, or any other mechanism. They are merged into `excluded_dirs` unconditionally during config model initialization.

---

### Two-Pass Pipeline {#two-pass-pipeline}

Zenzic's core analysis architecture. The pipeline processes each Markdown file in two sequential passes:

- **Pass 1 (Harvest + Credential Scan)** -- Stream every line; record `[id]: url` reference definitions; run the credential scanner on every line (including fenced code blocks and frontmatter). Populate the Reference Map.
- **Pass 2 (Cross-Check)** -- Resolve every `[text][id]` usage against the complete Reference Map. Flag undefined IDs as `DANGLING_REF`.
- **Pass 3 (Integrity Report)** -- Compute the per-file integrity score. Append Dead Definition and alt-text warnings.

Pass 2 only begins when Pass 1 completes without credential scanner findings.

See: [Architecture -- Three-Phase Pipeline](../explanation/architecture#three-phase-pipeline)

---

### Virtual Site Map (VSM) {#vsm}

An in-memory projection of the URL paths that the build engine will serve. The VSM maps every source file to its canonical URL and assigns a routing status:

| Status | Meaning |
| :--- | :--- |
| `REACHABLE` | File is in the nav and will be served at its canonical URL |
| `ORPHAN_BUT_EXISTING` | File exists on disk but is not listed in the nav |
| `IGNORED` | File is in a private directory or an unlisted README -- the engine will never serve it |
| `CONFLICT` | Two or more files map to the same canonical URL (slug collision) |

The VSM is constructed once after Pass 1 using the adapter's `get_route_info()` method. It enables Zenzic to detect Ghost Routes and unreachable links without invoking the build engine.
