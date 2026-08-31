<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Configure Third-Party Editors (Neovim, Helix, Emacs)

While Zenzic provides an official thin-client extension for VS Code, the **Zenzic Language Server (ZLS)** implements standard Language Server Protocol (LSP v3.17) over `stdio` (JSON-RPC 2.0).

Any editor or IDE supporting LSP over `stdio` can launch `zenzic lsp` as a background language server process for Markdown (`.md` and `.mdx`) files.

---

## Editor Configuration Snippets

Below are verified configuration snippets for major third-party editors supporting Language Server Protocol (LSP) over `stdio`.

### Helix

In your Helix configuration file (`~/.config/helix/languages.toml`):

```toml title="~/.config/helix/languages.toml"
[[language]]
name = "markdown"
language-servers = ["zenzic-lsp"]

[language-server.zenzic-lsp]
command = "zenzic"
args = ["lsp"]
```

### Neovim

Using Neovim's native LSP client in `~/.config/nvim/init.lua`, via the declarative
`vim.lsp.config`/`vim.lsp.enable` pair (Neovim 0.11+):

```lua title="~/.config/nvim/init.lua"
vim.lsp.config("zenzic", {
  cmd = { "zenzic", "lsp" },
  filetypes = { "markdown", "mdx" },
  root_markers = { ".zenzic.toml", ".git" },
})
vim.lsp.enable("zenzic")
```

### Emacs (Eglot)

Using Emacs' built-in `Eglot` package in `~/.emacs.d/init.el`:

```elisp title="~/.emacs.d/init.el"
(with-eval-after-load 'eglot
  (add-to-list 'eglot-server-programs
               '((markdown-mode gfm-mode) . ("zenzic" "lsp"))))
```

---

## Environment & Diagnostic Verification

Before configuring your editor, verify that `zenzic` is installed and accessible in your shell `$PATH`:

```bash title="Terminal"
# Output runtime environment diagnostics
zenzic env
```

To verify LSP `stdio` communication directly from your shell, run an inline JSON-RPC `shutdown` request:

```bash title="Terminal"
printf 'Content-Length: 44\r\n\r\n{"jsonrpc":"2.0","id":1,"method":"shutdown"}' | zenzic lsp
```

A properly working server immediately emits the JSON-RPC response on `stdout`:

```http
Content-Length: 38
Content-Type: application/vscode-jsonrpc; charset=utf-8

{"jsonrpc":"2.0","id":1,"result":null}
```

!!! note "Interactive Terminal Behavior"
    When `zenzic lsp` is launched directly in an interactive terminal shell (without stdin piping), it detects a TTY, displays an informational notice on `stderr`, and waits for `Ctrl+C` to exit cleanly.

---

## Explain a Suppression Without Editing the File

Hovering a `<!-- zenzic:ignore: CODE -->` comment reports what that directive is actually
doing — whether it suppresses a real finding, is redundant with a `.zenzic.toml` policy, or
has no effect at all because the code is inviolable. Hovering a live diagnostic also states
whether an inline comment could silence it in the first place.

This works in any LSP client that supports `textDocument/hover`; no VS Code-specific
feature is involved, and every snippet above enables it automatically. The
[Suppression Policy Reference](../reference/suppression-policy.md#inspecting-a-suppression-in-your-editor)
lists what each response means.

---

## Report a Finding as a GitHub Issue (VS Code)

The official VS Code extension adds **`Zenzic: Report Finding as GitHub Issue`** to the
command palette. It opens your browser on a prefilled issue form carrying the finding code,
the file and line, the diagnostic message, and your extension and editor versions.

Invoke it with the cursor inside a finding to report that one directly; from anywhere else
it lists the file's findings and asks which to report.

The command opens a URL and nothing more. It never authenticates, stores a token, or calls
the GitHub API, so there is no sign-in step and no rate limit — and with no network it is
your browser that reports the failure, not your editor. Nothing is submitted until you
review the prefilled form and press **Submit**.

---

## Related Documents

* [CLI Reference](../reference/cli.md) — Reference documentation for `zenzic lsp` and `zenzic env`.
* [Finding Codes Index](../reference/finding-codes.md) — Index of all Z-Codes reported in editor diagnostics.
* [Suppression Policy Reference](../reference/suppression-policy.md) — What each hover response about a suppression means.
