---
title: "Zenzic v0.25.0: LSP Stabilization & Adapter-Driven Hot-Reloading"
slug: zenzic-v0250-lsp-stabilization
date: 2026-07-25
authors:
  - pythonwoods
description: >
  Zenzic v0.25.0 stabilizes Language Server Protocol (LSP) operations with centralized core governance filtering, adapter-driven configuration hot-reloading, and an updated BaseAdapter contract.
categories:
  - Releases
  - Engineering
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

Zenzic v0.25.0 stabilizes the Language Server Protocol (LSP) integration, guaranteeing strict diagnostic parity between CLI and editor sessions. This release introduces centralized core governance evaluation, adapter-driven configuration hot-reloading for live VSM updates, and an updated `BaseAdapter` contract.

<!-- more -->

## Diagnostic Parity and Centralized Governance

In prior releases, governance evaluation (`directory_policies` and `per_file_ignores`) was executed within the CLI runner pipeline post-scanning. When editing files in LSP mode, incremental single-file analysis paths occasionally bypassed global directory policies, creating diagnostic divergence between terminal runs and VS Code PROBLEMS panels.

Zenzic v0.25.0 eradicates this divergence by centralizing governance evaluation into `zenzic.core.governance`.

### Single-Source-of-Truth Filtering

The `IncrementalAnalysisEngine._analyze_file` pipeline now evaluates governance rules directly at the core engine level:

1. **Incremental Evaluation**: Every document edit evaluated by the LSP engine executes `apply_directory_policies()` and `apply_per_file_ignores()` before diagnostics are emitted.
2. **Determinism Guaranteed**: Whether a file is inspected via `zenzic check all` in CI or opened inside VS Code, identical findings are suppressed and reported.

---

## Adapter-Driven Config Hot-Reloading (`LSP-FIX-009`)

Documentation architecture configurations (`mkdocs.yml`, `zensical.toml`) evolve during development. Previously, modifying navigation structures or plugin settings in `mkdocs.yml` required restarting the Zenzic Language Server to rebuild the Virtual Site Map (VSM).

v0.25.0 introduces dynamic adapter-driven configuration watching to eliminate manual server restarts.

### Reactive VSM Synchronization

The LSP file watcher now queries active adapters for watched configuration targets:

- **Adapter Sovereignty**: The core engine does not hardcode configuration filenames. Each adapter declares its configuration dependencies via the `watched_config_files` contract property.
- **Hot-Reload Dispatch**: When `mkdocs.yml` or `mkdocs.yaml` is modified, the LSP server intercepts the change, invalidates cached route entries, and triggers an in-memory VSM rebuild across the entire workspace.
- **Zero-Latency Navigation Updates**: Re-indexed routes and navigational changes reflect in editor diagnostics immediately upon saving configuration changes.

---

## Breaking Change: `BaseAdapter` Contract Expansion

> [!WARNING]
> **Breaking Change for Third-Party Adapters**: `BaseAdapter` has been extended under **ADR-078-STRICT** to declare `@property watched_config_files`.

To support framework-agnostic configuration hot-reloading, the base adapter contract (`zenzic.core.adapters._base.BaseAdapter`) introduces a new property requirement:

```python
class BaseAdapter(ABC):
    # ...
    @property
    def watched_config_files(self) -> frozenset[str]:
        """Return the configuration filenames that trigger a VSM rebuild in LSP mode."""
        return frozenset()
```

### Migration Guide for Adapter Implementers

If you maintain a custom third-party adapter subclassing `BaseAdapter`:

1. Update your class definition to override `watched_config_files`:
   ```python
   @property
   def watched_config_files(self) -> frozenset[str]:
       return frozenset({"my-framework.config.json"})
   ```
2. First-party adapters (`MkDocsAdapter`, `ZensicalAdapter`) have been updated natively.

---

## Upgrading

To update Zenzic Core globally via `uv`:

```bash
uv tool install --force zenzic
```

The Zenzic VS Code extension updates automatically via the Visual Studio Marketplace.
