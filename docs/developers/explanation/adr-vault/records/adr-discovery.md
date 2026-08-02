---

sidebar_position: 1
description: "ADR 003: Design decision record for multi-source documentation discovery logic."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 003: Root Discovery Protocol (RDP)

**Status:** Active (2026-04-08)
**Deciders:** Architecture Lead
**Date:** 2026-03-01
**Amendment:** 2026-04-08

---

## Context

Zenzic does not operate on isolated files. Every check it runs — link
validation, orphan detection, asset resolution — is relative to a logical
entity called the **Workspace**. The Workspace has a single authoritative
boundary: the **project root**.

Without a known root, Zenzic cannot:

- Resolve absolute-style internal links (`/docs/page.md`) to physical files.
- Locate `.zenzic.toml` or a fallback engine config (`mkdocs.yml`, `zensical.toml`).
- Enforce the Virtual Site Map (VSM) scan scope — the oracle that determines

  what is a valid page and what is a Ghost Route.

- Avoid accidentally indexing files that belong to a parent project,

  a sibling repository, or the system root.

The root discovery mechanism must therefore be **deterministic**, **safe by
default**, and **engine-neutral** (independent of MkDocs, Zensical, or any
other build toolchain).

---

## Decision

`find_repo_root()` in `src/zenzic/core/scanner.py` walks upward from the
current working directory, checking each ancestor for one of two **root
markers** (first match wins):

| Marker | Rationale |
|--------|-----------|
| `.git/` | Universal VCS signal. If a `.git` directory exists, the user has explicitly defined a repository boundary. Zenzic respects this boundary as the project scan scope. |
| `.zenzic.toml` | Zenzic's own configuration file. Its presence is an unambiguous declaration that this directory is the analysis root, even in non-VCS environments. |

`mkdocs.yml`, `pyproject.toml`, and other engine-specific files are
deliberately **excluded** from root markers. Including them would couple the
discovery mechanism to a specific build engine, violating Pillar 1
(*Lint the Source, not the Build*).

If no marker is found in any ancestor, `find_repo_root()` raises a
`RuntimeError` with an actionable message — it never silently defaults to the
filesystem root.

---

## Rationale

The technical rationale and architectural context driving this design decision are outlined below.


### 1. Safety: Preventing Accidental Massive Indexing

A naive implementation that defaults to the current directory when no marker
is found would allow a user invoking `zenzic check all` from `/home/user/` to
inadvertently index their entire home directory. The strict failure mode is
an **opt-out-of-danger** default: Zenzic refuses to act until the user
establishes a scan scope.

### 2. Consistency: Future `.gitignore` Support

Using `.git` as the root anchor aligns Zenzic's workspace boundary with the
VCS boundary. This is a prerequisite for any future feature that needs to
parse `.gitignore` (e.g. automatic exclusion of `site/`, `dist/`, or
generated build artifacts listed there).

### 3. User Experience: Predictable, Loud Failure

An ambiguous root produces incorrect results silently. A loud failure at
startup — before any file is touched — is preferable to a scan that reports
phantom violations or misses files because the root was resolved to the wrong
ancestor. The error message includes the CWD and an explicit remediation
hint.

### 4. Engine Neutrality

`.git` and `.zenzic.toml` are both engine-neutral markers. The same root
discovery logic works identically whether the project is built with MkDocs,
Zensical, Hugo, or plain Pandoc. This preserves the core invariant that
Zenzic's behaviour is independent of the build toolchain.

---

## Consequences

- **Positive:** Every code path that calls `find_repo_root()` is guaranteed

  to receive a valid, bounded directory or raise before any I/O occurs.

- **Positive:** Ghost Route logic and VSM construction have a stable anchor.
- **Negative (pre-amendment):** The `zenzic init` command, whose purpose is

  to *create* the `.zenzic.toml` root marker, could not be run in a directory
  that had neither `.git` nor `.zenzic.toml`. This was the **Bootstrap
  Paradox** (ZRT-005).

---

## Amendment — ZRT-005: The Genesis Fallback (2026-04-08)

**Problem:** `zenzic init` is the bootstrap command for new projects. Its
entire purpose is to create the `.zenzic.toml` root marker. Requiring a root
marker to *already exist* before `init` can run is a Catch-22.

**Resolution:** `find_repo_root()` gains a keyword-only parameter `fallback_to_cwd` (default `False`). When `fallback_to_cwd=True` and no root marker is found, the function returns `Path.cwd()` instead of raising. This is called the **Genesis Fallback**.

For the parameter specification, see [API Reference — `find_repo_root`](../../../reference/adapter-api.md#find_repo_root-fallback_to_cwd-bool--false---path).

**Authorisation scope:** The Genesis Fallback is a single-point exemption. Only the `init` command passes `fallback_to_cwd=True` (in `src/zenzic/cli/_standalone.py`). Every other command (`check`, `guard`, `score`, `diff`, `clean`) retains the strict default (`fallback_to_cwd=False`) and will continue to fail loudly outside a project scan scope.

**Security note:** The Genesis Fallback does **not** weaken the scan scope
for analysis commands. `zenzic check all` run from `/home/user/` with no
`.git` ancestor will still raise `RuntimeError`. The fallback is restricted
to the one command that is explicitly designed to establish a scan scope from
scratch.

---

## References

- `src/zenzic/core/scanner.py` — `find_repo_root()` implementation
- `src/zenzic/cli/_standalone.py` — `init` command, sole consumer of `fallback_to_cwd=True`
- `tests/test_scanner.py` — `test_find_repo_root_genesis_fallback`,

  `test_find_repo_root_genesis_fallback_still_raises_without_flag`

- `tests/test_cli.py` — `test_init_in_fresh_directory_no_git`
- `CONTRIBUTING.md` — Core Laws → Root Discovery Protocol
