# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the `zenzic lsp` CLI command (zenzic.cli._lsp.lsp).

These target the command wrapper itself (tty banner branch, KeyboardInterrupt
handling, exit-code propagation) — the LanguageServer's own protocol behavior
is covered exhaustively elsewhere (tests/test_lsp.py).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import typer

from zenzic.cli._lsp import lsp


def _mock_server(exit_code: int = 0, side_effect: BaseException | None = None) -> MagicMock:
    server = MagicMock()
    server.exit_code = exit_code
    if side_effect is not None:
        server.serve.side_effect = side_effect
    return server


def test_lsp_non_tty_skips_banner_and_propagates_exit_code() -> None:
    server = _mock_server(exit_code=0)
    with (
        patch("zenzic.cli._lsp.sys.stdin") as mock_stdin,
        patch("zenzic.cli._lsp.sys.stderr") as mock_stderr,
        patch("zenzic.cli._lsp.LanguageServer", return_value=server) as mock_cls,
    ):
        mock_stdin.isatty.return_value = False
        with pytest.raises(typer.Exit) as exc_info:
            lsp()

    mock_stderr.write.assert_not_called()
    server.serve.assert_called_once()
    assert mock_cls.call_args.kwargs["stdin"] is mock_stdin.buffer
    assert exc_info.value.exit_code == 0


def test_lsp_tty_prints_editor_banner_to_stderr() -> None:
    server = _mock_server(exit_code=0)
    with (
        patch("zenzic.cli._lsp.sys.stdin") as mock_stdin,
        patch("zenzic.cli._lsp.sys.stderr") as mock_stderr,
        patch("zenzic.cli._lsp.LanguageServer", return_value=server),
    ):
        mock_stdin.isatty.return_value = True
        with pytest.raises(typer.Exit):
            lsp()

    mock_stderr.write.assert_called_once()
    banner = mock_stderr.write.call_args[0][0]
    assert "Zenzic Language Server (ZLS)" in banner
    mock_stderr.flush.assert_called_once()


def test_lsp_keyboard_interrupt_is_swallowed_and_still_exits() -> None:
    server = _mock_server(exit_code=0, side_effect=KeyboardInterrupt())
    with (
        patch("zenzic.cli._lsp.sys.stdin") as mock_stdin,
        patch("zenzic.cli._lsp.LanguageServer", return_value=server),
    ):
        mock_stdin.isatty.return_value = False
        with pytest.raises(typer.Exit) as exc_info:
            lsp()

    assert exc_info.value.exit_code == 0


def test_lsp_nonzero_server_exit_code_propagates() -> None:
    server = _mock_server(exit_code=1)
    with (
        patch("zenzic.cli._lsp.sys.stdin") as mock_stdin,
        patch("zenzic.cli._lsp.LanguageServer", return_value=server),
    ):
        mock_stdin.isatty.return_value = False
        with pytest.raises(typer.Exit) as exc_info:
            lsp()

    assert exc_info.value.exit_code == 1
