---

description: "Package layout, module responsibilities, the Visual State Manager, and how to add commands to the Zenzic CLI."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CLI Architecture

The CLI is organised as a **package** (`src/zenzic/cli/`) rather than a single module.
Each file owns one domain of responsibility.

---

## Module Map

| Module | Responsibility |
|:-------|:---------------|
| `_audit.py` | `audit` command — Governance Audit / Technical Debt Ledger |
| `_check.py` | `check_app` Typer sub-app + seven `check *` commands; private helpers re-exported from `_governance.py`, `_target_resolver.py`, and `_command_setup.py` |
| `_clean.py` | `clean_app` Typer sub-app + `clean assets` command |
| `_command_setup.py` | `setup_command()` factory — consolidates repo-root discovery, config loading, target resolution, and exclusion-manager construction used by all check commands |
| `_config_explain.py` | `explain` command + config genealogy / rule introspection surface |
| `_env.py` | `env` command — environment diagnostics (ADR-075 Radical Unawareness) |
| `_fix.py` | `fix` command — AST Auto-Fix |
| `_governance.py` | `config_app` Typer sub-app + governance profile commands + per-file-ignore and directory-policy filter helpers (`_apply_per_file_ignores`, `_apply_directory_policies`) |
| `_guard.py` | `guard_app` Typer sub-app + `scan` / `init` commands for the fast secret guard |
| `_inspect.py` | `inspect_app` Typer sub-app + `capabilities`, `codes`, and `routes` commands |
| `_lab.py` | `lab` command + interactive scenario showcase |
| `_lsp.py` | `lsp` command — starts the Zenzic Language Server (ZLS) |
| `_metadata.py` | Single source of truth for root help panels, command grouping, and short help text |
| `_shared.py` | `console` singleton, `_ui` singleton, `configure_console()`, and all cross-command utilities (`_build_exclusion_manager`, `_output_json_findings`, `_render_link_error`, etc.) |
| `_standalone.py` | `score`, `diff`, and `init` commands + their private helpers |
| `_target_resolver.py` | `_resolve_target()` and `_apply_target()` — path lookup and config-patching helpers shared by check commands and the lab command |
| `templates.py` | TOML template constants for `zenzic init` — layout/scaffold text kept separate from generator logic (SRP) |
| `__init__.py` | Public re-export surface consumed by `main.py` — **do not add logic here** |

`main.py` is the unified Typer registration factory. New top-level commands and sub-apps
must be registered there, and root help metadata must stay aligned with `_metadata.py`.

---

## The Visual State Manager

`_shared.py` is the **sole owner of all console and UI state**. This is the most critical
architectural rule in the CLI layer:

> **PROHIBITION:** No command module may instantiate `Console()` or a custom UI class
> directly. All output must go through `get_ui()` and `get_console()` from `_shared.py`.

```python
# ✅ Correct — in any _check.py / _clean.py / _standalone.py command
from . import _shared

_shared.get_ui().print_header(__version__)
_shared.get_console().print("output")

# ❌ FORBIDDEN — never do this in a command module
from rich.console import Console
from mypackage.ui import LegacyInterfaceV1

console = Console(...)  # breaks shared state
ui = LegacyInterfaceV1(console)  # creates an orphaned instance
```

For the design rationale behind UI state sharing, see [ADR 004 — Unified Console State](../explanation/adr-vault/records/adr-decentralized-cli.md#4-unified-console-state-visual-state-manager).

**UI output conventions:**

- Always use `ZenzicPalette.DIM` for dim/secondary text — never the raw Rich tag `[dim]`.
- Vertical spacing: compact (Ruff-style). No blank lines between individual footer lines. Use `Rule()` separators only to divide major report sections.
- New symbols must be added to `_EMOJI` in `zenzic/core/ui.py` before use — never inline Unicode literals.

---

## Adding CLI Commands

For step-by-step instructions on how to add commands or new sub-apps to the CLI, see [Writing a New Check — CLI Wiring](../how-to/write-a-check.md#cli-wiring).

---

## Exit Codes

The CLI exits with one of four codes. These are frozen — do not add new exit codes without
an explicit architecture decision:

| Code | Meaning |
|:----:|:--------|
| `0` | All checks passed |
| `1` | Quality issues found |
| `2` | SECURITY — leaked credential detected |
| `3` | SECURITY — system-path traversal detected |

`PLUGIN_FORBIDDEN_EXITS` enforces that third-party adapters cannot emit exit codes outside
this set. See the [Adapter API reference](./adapter-api) for the full contract.
