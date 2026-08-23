---
description: "Architectural Decision Record mandating non-inline suppression for topological and graph-level findings and codifying LSP UX determinism."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 093: Topological Suppression Non-Inline Invariant & LSP UX Determinism

This document details the architectural specification and contract for ADR 093: Topological Suppression Non-Inline Invariant & LSP UX Determinism within the Zenzic ecosystem.

---

## Context

Findings emitted by static analysis engines fall into two fundamentally distinct semantic domains:

1. **Line-Anchored Content Findings** (`Z1xx`, `Z403`, `Z5xx`, `Z6xx`): Bound to a concrete text token, HTML element, heading, or code fence on a specific line number.
2. **Graph-Level & File-Level Topological Findings** (`Z401`, `Z402`, `Z404`, `Z405`, `Z406`, `Z410`, `Z411`, `Z412`, `Z620`): Bound to the global Virtual Site Map (VSM), navigation manifests, or workspace boundary.

Historically, inline HTML comments (`<!-- zenzic:ignore: Zxxx -->` and `data-zenzic-ignore="Zxxx"`) were loosely permitted across several topological codes (`Z410`, `Z411`). This produced an architectural contradiction. Suppressing a graph-level defect on line 1 of a file corrupted local content semantics and obscured global debt. Furthermore, it confused Language Server (LSP) users who received Quick Fixes that appeared to succeed but failed to alter graph topology.

---

## Decision

1. **Topological Non-Inline Invariant**:
   Graph-level and file-level findings are codified as `NON_INLINE_SUPPRESSIBLE_CODES`:

   ```python
   NON_INLINE_SUPPRESSIBLE_CODES = frozenset(
       {
           "Z401",  # MISSING_DIRECTORY_INDEX
           "Z402",  # ORPHAN_PAGE
           "Z404",  # CONFIG_ASSET_MISSING
           "Z405",  # UNUSED_ASSET
           "Z406",  # NAV_CONTRACT
           "Z410",  # UNREACHABLE_GRAPH_NODE
           "Z411",  # DEAD_END_NODE
           "Z412",  # TRACEABILITY_BROKEN
           "Z620",  # STALE_GLOBAL_SUPPRESSION
       }
   )
   ```

   Inline suppression comments (Markdown `<!-- zenzic:ignore: Zxxx -->` or HTML `data-zenzic-ignore="Zxxx"`) are strictly forbidden and non-functional for these codes.

2. **Explicit TOML Governance**:
   Topological findings can ONLY be suppressed through centralized configuration in `.zenzic.toml` using `[governance.directory_policies]` or `[governance.per_file_ignores]`.

3. **Preservation of `Z403` (`MISSING_ALT`)**:
   `Z403` is anchored to a concrete `<img>` or `![]()` element on a specific line of Markdown and remains inline-suppressible.

4. **LSP UX Determinism via `disabled.reason`**:
   The Language Server Protocol server (`src/zenzic/lsp/server.py`) must NOT emit line-insertion QuickFix edits for `NON_INLINE_SUPPRESSIBLE_CODES`. Instead, it emits an informative CodeAction utilizing the LSP 3.16+ `disabled.reason` specification:

   ```json
   {
     "title": "Suppress Z412 (configure via .zenzic.toml)",
     "kind": "quickfix",
     "disabled": {
       "reason": "Z412 is a topological finding. Configure suppression in .zenzic.toml via [directory_policies] or [per_file_ignores]."
     }
   }
   ```

---

## Rationale

Topological findings represent systemic structure rather than localized typographical syntax.

### Why Not Automated `WorkspaceEdit` on `.zenzic.toml`?

Injecting configuration lines into `.zenzic.toml` automatically from the LSP was rejected for critical architectural reasons:

- **TOML Root Key Law**: Under TOML 1.0 specifications and Zenzic configuration contracts, root-level keys (`docs_dir`, `fail_under`) must strictly precede table headers (`[...]`). Automated text insertion into unparsed TOML files risks placing root keys below tables or malforming table headers.
- **Comment & Formatting Preservation**: Modifying TOML without full round-trip AST preservation strips developer comments and custom spacing.
- **Intentionality of Governance**: Topological debt represents structural decisions that require deliberate engineering oversight, not casual one-click editor suppression.

Using the LSP `disabled.reason` protocol provides complete UX transparency, guides the developer to the correct configuration path, and eliminates any risk of configuration corruption.

---

## Invariants

- No rule card in `docs/rules/` for `NON_INLINE_SUPPRESSIBLE_CODES` may document inline comment suppressions.
- The LSP server must never offer active inline text edits for `NON_INLINE_SUPPRESSIBLE_CODES`.
- `Z403` must remain inline-suppressible.
- All gallery examples in `examples/` must demonstrate TOML governance for topological findings.

---

## Consequences

- Full alignment between the CLI, the LSP engine, and user documentation.
- Elimination of dead or misleading inline suppression comments in repositories.
- Deterministic and auditable documentation quality governance.

For operational protocols, see the [Release Governance Protocol](../../../how-to/release-governance-protocol.md) and the [ADR Vault Records Index](./index.md).
