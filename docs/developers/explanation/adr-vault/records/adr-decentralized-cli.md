---

sidebar_position: 7
description: "ADR 004: Splitting the monolithic CLI module into a structured package — the Layer Law that keeps Core independent of CLI."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 004: Decentralized CLI Package

**Status:** Active
**Decider:** Architecture Lead
**Date:** 2026-04-15 (D062-B / D063 / D064)

---

## Context

Zenzic's original CLI lived in a single file: `src/zenzic/cli.py`. Over the
course of the current series release cycle, that file grew to exceed **2,000 lines**,
containing six conceptually distinct responsibilities in a single namespace:

| Responsibility | Examples |
|---|---|
| Analysis commands | `check links`, `check orphans`, `check all` |
| Engine inspection | `inspect capabilities` |
| Maintenance commands | `clean` |
| Lab showcase | `zenzic lab` — 11 interactive acts |
| Standalone operations | `diff`, `score`, `init` |
| Shared UI/output helpers | banner, console, exclusion manager builder |

This monolith created compounding problems:

1. **Circular import risk.** As `core/` modules grew, contributors were tempted

   to import `cli.py` utilities directly from core, inverting the dependency
   direction.

2. **UI state scattering.** The Rich `console` object was instantiated multiple

   times across different function scopes, causing inconsistent output formatting
   and race conditions in test environments.

3. **Test isolation failure.** Every test that touched any CLI command had to

   import the entire `cli.py` — including the lab showcase, the Rich live display,
   and all Typer sub-apps. This inflated test startup time and made mocking
   unreliable.

4. **Contributor friction.** A new contributor adding a check command had no

   clear "where does this go?" signal from the file structure alone.

---

## Decision

`src/zenzic/cli.py` was dissolved into a package `src/zenzic/cli/` with the
following module structure:

```text
src/zenzic/cli/
  __init__.py       — public re-exports
  _check.py         — check sub-app: links, orphans, snippets, references, assets, all
  _inspect.py       — inspect sub-app: capabilities
  _clean.py         — clean sub-app
  _lab.py           — lab command: 11 Acts (0–10), interactive showcase
  _standalone.py    — standalone commands: diff, init, score
  _shared.py        — shared helpers: _build_exclusion_manager, _validate_docs_root,
                      _ui, console
```

`src/zenzic/main.py` became the **Typer entry point** — a thin orchestrator
that imports each sub-app and registers it on the root Typer application. It
contains no analysis logic.

Three companion decisions were applied in the same release:

- **D062-B:** `src/zenzic/ui.py` → `src/zenzic/core/ui.py`. UI primitives are

  consumed by both CLI and Core; placing them in `core/` ensures Core can use
  them without importing from `cli/`, which would violate the Layer Law.

- **D063:** `src/zenzic/lab.py` → `src/zenzic/cli/_lab.py`. The lab showcase is

  pure CLI orchestration — interactive Rich displays, act sequencing, user
  prompts. It belongs with the CLI layer, not adjacent to the core.

- **D064 (SDK Cleansing):** `run_rule()` was extracted from `cli.py` into

  `core/rules.py`. The public `zenzic.rules` module became a **6-line re-export
  façade** — backwards compatible for any third-party code that imported it
  directly, while ensuring the implementation lives in `core/`.

---

## The Layer Law (Rule R05)

This ADR formalises the **dependency direction invariant** as a named rule:

> **R05 — Core never imports upward.** Modules in `src/zenzic/core/` must never
> import from `src/zenzic/cli/` or `src/zenzic/main.py`.

The enforced direction is:

```text
cli/ → core/ → models/
```

`cli/` may import anything from `core/`. `core/` may import from `models/`. The
reverse is permanently forbidden. This ensures that `core/` can be used as a
standalone SDK without dragging in Typer, Rich live displays, or any interactive
I/O dependencies.

---

## Rationale

The technical rationale and architectural context driving this design decision are outlined below.

### 1. Single Responsibility at the File Level

A 2,000-line file is not a file — it is an undeclared package. Formalising the
package structure makes the single-responsibility principle visible in the
filesystem: a contributor looking for orphan-detection logic opens `_check.py`,
not a monolith where they must search by function name.

### 2. Test Isolation

After the split, `test_cli.py` can import only the specific sub-app under test.
The lab showcase's Rich live displays are no longer loaded when testing `check
links`. Startup time for individual test modules dropped measurably.

### 3. SDK Contract

The `zenzic.rules` façade preserves backwards compatibility for any project that
used `from zenzic.rules import run_rule`. No import path changes were required for
existing integrations, despite the internal reorganisation.

### 4. Unified Console State (Visual State Manager)

Instantiating multiple `Console()` objects across different command modules breaks the command-line argument overrides. When `--no-color` or `--force-color` is passed, `configure_console()` overrides the singletons in `_shared.py`. Any locally-instantiated `Console` would bypass this configuration, leading to mixed-mode coloring or ignored user preferences.

---

## Invariants (Non-Negotiable)

- `src/zenzic/core/` never imports from `src/zenzic/cli/` — any PR that introduces

  such an import is an automatic revert candidate.

- `_shared.py` is the **only** place in `cli/` where the Rich `console` object is

  instantiated. All other `cli/` modules call `_ui()` from `_shared.py`.

- `src/zenzic/main.py` contains **no analysis logic** — only Typer app wiring.
- `zenzic.rules` remains a re-export façade. The implementation lives in

  `core/rules.py`.

---

## Consequences

- New CLI commands are added to the appropriate `cli/_*.py` module, not to a

  catch-all monolith.

- The `run_rule()` function is importable as both `zenzic.rules.run_rule` (public

  façade) and `zenzic.core.rules.run_rule` (direct). Both paths are stable.

- The lab showcase (`cli/_lab.py`) can be extended with new acts without

  affecting the analysis pipeline's test surface.

---

## Companion Decision D082 — CLI Decomposition

**Status:** Accepted — v0.8.0

**Context:** `_check.py` had grown to 1641 lines, accumulating four categories of
helper that properly belong elsewhere: governance filters, target resolution, command
setup boilerplate, and the governance reporting already in `_governance.py`.

**Decision:** Extract helpers into dedicated modules with backward-compatible re-exports.

| New module | Extracted from | Functions |
|:-----------|:---------------|:----------|
| `_governance.py` | `_check.py` | `_apply_per_file_ignores`, `_apply_directory_policies` |
| `_target_resolver.py` | `_check.py` | `_resolve_target`, `_apply_target` |
| `_command_setup.py` | `_check.py` | `setup_command()` factory |

**Zero-Regression Contract:** 1550 tests pass unchanged. All moved symbols remain
importable from `_check.py` via re-export stubs, so any downstream code that imports
directly from `_check` continues to work without modification.

**Outcome:** `_check.py` reduced from 1641 → 1478 lines. Each new module has a single,
clearly-named responsibility consistent with this ADR's decentralised-ownership model.
