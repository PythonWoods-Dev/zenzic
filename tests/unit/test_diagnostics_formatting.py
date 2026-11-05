# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ZenzicDiagnostic LSP payload serialization (ZLS-UX-001-DIAGNOSTIC-FORMATTING)."""

from __future__ import annotations

from zenzic.models.diagnostics import (
    DiagnosticPosition,
    DiagnosticRange,
    Severity,
    ZenzicDiagnostic,
)


def test_to_lsp_dict_formatting() -> None:
    """Verify that to_lsp_dict prepends [Z-Code] to message and includes codeDescription href."""
    diag = ZenzicDiagnostic(
        range=DiagnosticRange(
            start=DiagnosticPosition(line=0, character=0),
            end=DiagnosticPosition(line=0, character=10),
        ),
        severity=Severity.ERROR,
        code="Z101",
        source="zenzic",
        message="'missing.md' resolves to nowhere",
    )

    lsp_dict = diag.to_lsp_dict()

    assert lsp_dict["code"] == "Z101"
    assert lsp_dict["message"] == "[Z101] 'missing.md' resolves to nowhere"
    assert lsp_dict["codeDescription"] == {
        "href": "https://zenzic.dev/reference/finding-codes/#z101",
    }
    assert lsp_dict["source"] == "zenzic"
    assert lsp_dict["severity"] == 1
    assert lsp_dict["range"] == {
        "start": {"line": 0, "character": 0},
        "end": {"line": 0, "character": 10},
    }


def test_internal_message_immutability() -> None:
    """Verify that calling to_lsp_dict does not alter the internal dataclass message attribute."""
    original_message = "Broken link target: /nonexistent.md"
    diag = ZenzicDiagnostic(
        range=DiagnosticRange(
            start=DiagnosticPosition(line=5, character=2),
            end=DiagnosticPosition(line=5, character=20),
        ),
        severity=Severity.WARNING,
        code="Z203",
        source="zenzic",
        message=original_message,
    )

    # Invoke serialization
    lsp_dict = diag.to_lsp_dict()

    # Core internal dataclass message attribute must remain unchanged
    assert diag.message == original_message
    assert diag.message != lsp_dict["message"]
    assert lsp_dict["message"] == f"[Z203] {original_message}"


def test_to_lsp_dict_keys_schema() -> None:
    """Verify exact JSON keys generated in to_lsp_dict for LSP 3.16/3.17 compliance."""
    diag = ZenzicDiagnostic(
        range=DiagnosticRange(
            start=DiagnosticPosition(line=1, character=1),
            end=DiagnosticPosition(line=1, character=5),
        ),
        severity=Severity.HINT,
        code="Z501",
        source="zenzic",
        message="Style suggestion",
    )

    lsp_dict = diag.to_lsp_dict()
    expected_keys = {"range", "severity", "code", "codeDescription", "source", "message"}
    assert set(lsp_dict.keys()) == expected_keys
