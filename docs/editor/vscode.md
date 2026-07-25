<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Zenzic VS Code Extension

The official **Zenzic VS Code Extension** (`pythonwoods.zenzic-vscode`) brings sub-50ms deterministic diagnostics, credential scanning, and real-time topological validation directly into your authoring environment.

## Thin Client Architecture

The extension is designed as a **Thin Client**. It contains zero parsing engines, zero regex logic, and zero validation rules.

Instead, it relies on the Language Server Protocol (LSP) over `stdio` to communicate directly with your local Zenzic Python binary (`zenzic lsp`). This guarantees 100% parity between local editor feedback and CI/CD pipeline enforcement.

```text
┌─────────────────────────┐   JSON-RPC 2.0 (stdio)   ┌──────────────────────────────┐
│  VS Code Extension      ├─────────────────────────►│  Zenzic Language Server      │
│  (pythonwoods-vscode)   │◄─────────────────────────┤  (zenzic lsp)                │
└─────────────────────────┘                          └──────────────────────────────┘
```

## Requirements & Baseline

- **Zenzic Core**: v0.23.1 or higher installed on your system or virtual environment.
- **VS Code**: v1.125.0 or higher.

## Installation

### 1. Install the Core Engine

The VS Code extension requires the Zenzic Python core binary to perform analysis:

```bash
uv tool install --force zenzic
```

Alternatively, install via `pip` or inside your active virtual environment:

```bash
pip install zenzic
```

### 2. Install the Extension

Search for **Zenzic** in the VS Code Extensions panel (`Ctrl+Shift+X` / `Cmd+Shift+X`), or install via the VS Code CLI:

```bash
code --install-extension pythonwoods.zenzic-vscode
```

## Configuration

The extension automatically discovers `zenzic` in standard `$PATH` directories and user bin locations (`~/.local/bin`, `~/.cargo/bin`, `~/.uv/bin`).

If you use a custom virtual environment or isolated installation, configure `zenzic.executablePath` in your VS Code `settings.json`:

```json
{
  "zenzic.executablePath": "${workspaceFolder}/.venv/bin/zenzic"
}
```

### Supported Settings

| Setting | Type | Default | Description |
|---|---|---|---|
| `zenzic.executablePath` | `string` | `"zenzic"` | Absolute path or binary name for the Zenzic executable. |

## Domain Boundaries & Supported Files

To uphold **Domain-Aware Discovery** and **Radical Unawareness**:

- **File Extensions**: The extension and Language Server exclusively target Markdown (`.md`) and MDX (`.mdx`) files. Non-documentation files (e.g. `OWNERS`, `.gitignore`, `config.yaml`) are automatically filtered out.
- **Configured Domain**: Only files residing within the configured `docs_dir` (default: `docs/`) or `extra_content_roots` are evaluated. Out-of-bounds files in the workspace (such as root `README.md` when `docs_dir = "docs"`) produce zero diagnostics.

> **Having issues?** See the [Troubleshooting Guide](../how-to/troubleshooting.md#editor-integration).
