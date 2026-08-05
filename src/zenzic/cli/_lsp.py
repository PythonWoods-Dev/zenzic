# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""CLI command for the Zenzic Language Server (ZLS)."""

from __future__ import annotations

import sys

import typer

from zenzic.lsp.server import LanguageServer


def lsp() -> None:
    """Start the Zenzic Language Server (ZLS) over stdio.

    This command initializes the JSON-RPC server loop and binds it to
    sys.stdin.buffer and sys.stdout.buffer for editor clients.
    """
    if sys.stdin.isatty():
        sys.stderr.write(
            "Zenzic Language Server (ZLS) running over stdio.\n"
            "This command is intended for editor clients (VS Code, Neovim, Helix, Emacs).\n"
            "Press Ctrl+C to exit.\n"
        )
        sys.stderr.flush()

    server = LanguageServer(stdin=sys.stdin.buffer, stdout=sys.stdout.buffer)
    try:
        server.serve()
    except KeyboardInterrupt:
        pass
    raise typer.Exit(code=server.exit_code)
