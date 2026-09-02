---

description: "Step-by-step guide to adding a new check to the Zenzic analysis engine, including the Core Laws every contributor must honour."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Writing a New Check

Zenzic's checks live in `src/zenzic/core/`. Each check is a standalone function in either
`scanner.py` (filesystem traversal) or `validator.py` (content validation). CLI wiring is
in the `cli/` package (`src/zenzic/cli/`).

---

## Six-Step Checklist

1. **Implement** the logic in the appropriate core module (`zenzic.core.scanner` or `zenzic.core.validator`).
2. **Delegate resolution** to `InMemoryPathResolver` — never call `os.path.exists()`, `Path.is_file()`, or any other filesystem probe inside a per-link loop. The resolver is instantiated once before the loop; re-instantiation per file defeats the pre-computed `_lookup_map` and drops throughput from 430 000+ to below 30 000 resolutions/s.
3. **Test i18n** — if the check involves file paths, test it in all three i18n configurations (none, folder mode, suffix mode).
4. **Wire the CLI** — add a corresponding command or sub-command in the `cli/` package. See the [CLI Architecture reference](../reference/cli-architecture). If your command accepts a `PATH` argument, you must call `find_repo_root(search_from=resolved_path)` and invoke `_apply_target()` to respect Path Sovereignty.
5. **Write tests** in `tests/` covering both passing and failing cases, including a performance baseline (5 000 links resolved in < 100 ms against a mock in-memory corpus).
6. **Update examples** in `examples/` to exercise the new check — Zenzic validates its own examples on every commit.

> **Performance contract:** the `zenzic.core` hot path must remain allocation-free. No `Path`
> object construction, no syscalls, and no `relative_to()` calls inside the resolution loop.

---

## Core Laws

All checks must respect the Core Laws governing the scanner. Before writing a check, ensure you are familiar with the invariants detailed in the [Core Laws of the Scanner](../explanation/core-laws.md).

---

## CLI Wiring

Depending on whether you are adding a command to an existing sub-app or introducing a new top-level sub-app, follow the steps below:

### Adding a Command to an Existing Sub-App

In the appropriate sub-app module (e.g., `src/zenzic/cli/_check.py`):

```python
@check_app.command(name="metadata")
def check_metadata(path: Path = ...) -> None: ...
```

No changes to `__init__.py`, `main.py`, or `_metadata.py` are required.

### Adding a New Top-Level Sub-App

1. Create a new module `src/zenzic/cli/_myfeature.py` defining the sub-app: `myfeature_app = typer.Typer(...)`.
2. Export `myfeature_app` from `src/zenzic/cli/__init__.py`.
3. Register the sub-app in `src/zenzic/main.py`: `app.add_typer(myfeature_app, name="myfeature", rich_help_panel="...")`.
4. Add a `CommandMeta(...)` entry in `src/zenzic/cli/_metadata.py` so root help panels and short help stay authoritative.
5. If the sub-app uses `no_args_is_help=True`, add `"myfeature"` to the `_SUBAPPS_WITH_MENU` frozenset in `cli_main()` so the Zenzic banner appears when the sub-app is invoked with no arguments.

---

## Credential Scanner Obligations

If your check touches the credential scanner or `harvest()`, see the dedicated
[Credential Scanner Obligations](../reference/credential-scanner-obligations) reference.
The four obligations are Worker Timeout, Regex-Canary, the Dual-Stream Invariant, and the
mutation score. The first three are enforced on every PR touching `src/zenzic/core/`. The
fourth is gated in CI as a no-regression floor rather than at its stated target: the
credential scanner currently measures **56.5%** against a target of **≥ 90%**, and closing
that gap is open work. The reference page explains what the gate does and does not promise.

---

## Finding Codes & Scoring Parity Protocol

Every new check must emit findings using a code registered in `CODE_DEFINITIONS` (`src/zenzic/core/codes.py`). When adding a new finding code, you MUST maintain 100% synchronization across **10 mandatory Mirror Law targets** (ADR-020) in the same PR:

1. **`src/zenzic/core/codes.py`**: Register the code in `CODE_DEFINITIONS` with severity, DQS penalty, category (`structural`, `navigation`, `content`, `brand`), and Opt-In metadata.
2. **`src/zenzic/core/scorer.py`**: If the code is a Governance rule (`Z6xx`), update the `_Z6XX_CODES` set for exponential escalation.
3. **`docs/reference/scoring-algorithm.md`**: Update the Complete Penalty Reference Table.
4. **`docs/explanation/scoring-system.md`**: Update the DQS Category Weight matrix and category mapping.
5. **`docs/reference/finding-codes.md`**: Add/update the encyclopedia catalog card with severity, penalty, category, Opt-In metadata, and remediation steps.
6. **`docs/rules/ZXXX.md`**: Create a dedicated rule specification card with explicit suppression mechanics.
7. **`mkdocs.yml`**: Register the new rule card under the Rule Specification Cards navigation section.
8. **`src/zenzic/cli/_lab.py` & `examples/`**: Create an interactive test fixture in `examples/` and register it in `_GALLERY` in `_lab.py`.
9. **`src/zenzic/cli/templates.py`**: Update the `zenzic init` configuration scaffold if the code introduces a new Policy-as-Code field.
10. **`../zenzic-vscode/zenzic.schema.json`**: Update the VS Code IntelliSense JSON Schema — this target lives in the sibling `zenzic-vscode` repository and needs a corresponding PR there.

Do not reuse retired codes. Also add an entry to `CHANGELOG.md` under `[Unreleased]` — not one of the 10 Mirror Law targets itself, but every user-facing finding code addition needs one regardless.
