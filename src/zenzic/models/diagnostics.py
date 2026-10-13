# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Strictly typed diagnostic payload for the Zenzic Language Server.

Design invariants:
- All fields are explicitly typed: ``Any`` is forbidden.
- Instances are the canonical in-memory representation of a diagnostic.
- Serialization to JSON-RPC format happens only at the transport boundary
  via ``to_lsp_dict()``, keeping the core model entirely wire-format-agnostic.
- ``Severity`` is an ``IntEnum`` to prevent magic-number drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Severity(IntEnum):
    """LSP-compatible diagnostic severity levels (§3.15.1 of the LSP spec)."""

    ERROR = 1
    WARNING = 2
    INFORMATION = 3
    HINT = 4


@dataclass(frozen=True)
class DiagnosticPosition:
    """Zero-indexed (line, character) position in a UTF-16 encoded document."""

    line: int
    character: int


@dataclass(frozen=True)
class DiagnosticRange:
    """Exclusive start-to-end range spanning a diagnostic in the source text."""

    start: DiagnosticPosition
    end: DiagnosticPosition


@dataclass(frozen=True)
class ZenzicDiagnostic:
    """Canonical, wire-format-agnostic diagnostic payload.

    Attributes:
        range:    Source range (UTF-16 columns) in which the violation occurs.
        severity: Severity level as defined in :class:`Severity`.
        code:     The Zenzic finding code (e.g. ``"Z101"``).
        source:   Constant identifier for the origin tool (``"zenzic"``).
        message:  Human-readable description of the violation.
    """

    range: DiagnosticRange
    severity: Severity
    code: str
    source: str
    message: str

    # ── Serialization boundary ────────────────────────────────────────────────

    def to_lsp_dict(
        self,
    ) -> dict[str, int | str | dict[str, str] | dict[str, dict[str, int]]]:
        """Serialize to the exact shape required by LSP ``publishDiagnostics``.

        This is the ONLY location in the codebase where a ``ZenzicDiagnostic``
        is converted to a plain dictionary.  All internal logic must operate on
        typed ``ZenzicDiagnostic`` instances.
        """
        return {
            "range": {
                "start": {
                    "line": self.range.start.line,
                    "character": self.range.start.character,
                },
                "end": {
                    "line": self.range.end.line,
                    "character": self.range.end.character,
                },
            },
            "severity": int(self.severity),
            "code": self.code,
            "codeDescription": {
                "href": f"https://zenzic.dev/reference/finding-codes/#{self.code.lower()}",
            },
            "source": self.source,
            "message": f"[{self.code}] {self.message}",
        }
