# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""In-memory Document Manager for incremental LSP synchronization."""

from __future__ import annotations

from typing import Any


class DocumentManager:
    """Manages the current state of documents opened in the editor via Incremental Sync."""

    def __init__(self) -> None:
        """Initialize an empty document registry."""
        self.documents: dict[str, str] = {}

    def did_open(self, params: dict[str, Any]) -> None:
        """Handle textDocument/didOpen notification."""
        doc = params.get("textDocument", {})
        uri = doc.get("uri")
        text = doc.get("text", "")
        if uri:
            self.documents[uri] = text

    def did_close(self, params: dict[str, Any]) -> None:
        """Handle textDocument/didClose notification."""
        doc = params.get("textDocument", {})
        uri = doc.get("uri")
        if uri in self.documents:
            del self.documents[uri]

    def did_change(self, params: dict[str, Any]) -> None:
        """Handle textDocument/didChange notification with incremental patch support."""
        doc = params.get("textDocument", {})
        uri = doc.get("uri")
        changes = params.get("contentChanges", [])
        if uri not in self.documents:
            return

        text = self.documents[uri]
        for change in changes:
            if "range" in change:
                # Incremental sync with UTF-16 offsets
                range_info = change["range"]
                start = range_info["start"]
                end = range_info["end"]
                # `.get` rather than `[...]`: a change object without "text"
                # raised KeyError, the server loop swallowed it, and the buffer
                # was left at its pre-change value while the editor moved on --
                # every later incremental patch then applied to a wrong base,
                # a permanent desync with no signal.
                text = self._apply_edit(text, start, end, change.get("text", ""))
            else:
                # Full sync fallback (if the editor decides to send a full string)
                text = change.get("text", "")

        self.documents[uri] = text

    def _to_index(self, text: str, line_idx: int, char_idx: int) -> int:
        """Convert an LSP (line, UTF-16 code unit column) position to a Python string index."""
        lines = text.splitlines(keepends=True)
        # A negative line index used to slice from the end -- `lines[:line_idx]`
        # computed a matching wrong prefix, so the edit landed at a plausible
        # but wrong offset with no error at all, and every subsequent diagnostic
        # was computed against content the editor does not have. Clamp instead.
        line_idx = max(0, line_idx)
        char_idx = max(0, char_idx)
        if line_idx >= len(lines):
            return len(text)

        line = lines[line_idx]
        col = 0
        python_idx = 0
        for c in line:
            if col >= char_idx:
                break
            python_idx += 1
            # UTF-16: characters outside BMP (> 0xFFFF) count as 2 code units
            col += 2 if ord(c) > 0xFFFF else 1

        prev_len = sum(len(line) for line in lines[:line_idx])
        return prev_len + python_idx

    def _apply_edit(
        self, text: str, start: dict[str, Any], end: dict[str, Any], new_text: str
    ) -> str:
        """Apply an incremental patch replacing the string between start and end."""
        start_idx = self._to_index(text, start.get("line", 0), start.get("character", 0))
        end_idx = self._to_index(text, end.get("line", 0), end.get("character", 0))

        # Ensure start_idx <= end_idx (robustness against inverted ranges)
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx

        return text[:start_idx] + new_text + text[end_idx:]
