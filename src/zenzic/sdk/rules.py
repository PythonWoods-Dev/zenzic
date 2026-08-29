# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Zenzic Custom Rule SDK v3 — Base rule contract and visitor interface."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zenzic.core.rules import BaseRule, RuleFinding
from zenzic.models.rules import RuleMetadata


if TYPE_CHECKING:
    pass


class ZenzicRuleV3(BaseRule):
    """Base class for Custom Rule SDK v3 rules.

    Subclass this class to create a custom, typed, deterministic Python rule
    for Zenzic.

    Attributes:
        metadata: Typed RuleMetadata defining code, title, severity, category, and penalty.
    """

    metadata: RuleMetadata

    def __init__(self, metadata: RuleMetadata | None = None) -> None:
        if metadata is not None:
            self.metadata = metadata
        if not hasattr(self, "metadata") or self.metadata is None:
            raise ValueError(
                f"Rule class {self.__class__.__name__} must define a RuleMetadata instance "
                f"or pass one to __init__."
            )

    @property
    def rule_id(self) -> str:
        """Return stable rule code from metadata."""
        return self.metadata.code

    def create_finding(
        self,
        file_path: Path,
        line_no: int,
        message: str,
        matched_line: str = "",
        col_start: int = 0,
        match_text: str = "",
    ) -> RuleFinding:
        """Construct a RuleFinding populated with the rule's metadata severity."""
        return RuleFinding(
            file_path=file_path,
            line_no=line_no,
            rule_id=self.metadata.code,
            message=message,
            severity=self.metadata.severity,
            matched_line=matched_line,
            col_start=col_start,
            match_text=match_text,
        )

    def check(self, file_path: Path, text: str) -> list[RuleFinding]:
        """Engine entry point for single file analysis.

        Invokes :meth:`visit_document`, :meth:`visit_line`, and AST node visitors
        if overridden by the subclass.
        """
        findings: list[RuleFinding] = []

        # 1. Document visitor
        doc_findings = self.visit_document(file_path, text)
        if doc_findings:
            findings.extend(doc_findings)

        # 2. Line visitor (if overridden)
        if self._is_method_overridden("visit_line"):
            lines = text.splitlines()
            for line_no, line_text in enumerate(lines, start=1):
                line_findings = self.visit_line(file_path, line_no, line_text)
                if line_findings:
                    findings.extend(line_findings)

        # 3. Link, Heading, and Code Block visitors (if overridden)
        if (
            self._is_method_overridden("visit_link")
            or self._is_method_overridden("visit_heading")
            or self._is_method_overridden("visit_code_block")
        ):
            self._execute_ast_visitors(file_path, text, findings)

        return findings

    def visit_document(self, file_path: Path, text: str) -> list[RuleFinding]:
        """Override to inspect full raw Markdown source text."""
        return []

    def visit_line(self, file_path: Path, line_no: int, line_text: str) -> list[RuleFinding]:
        """Override to inspect individual source lines line-by-line."""
        return []

    def visit_link(
        self, file_path: Path, line_no: int, link_text: str, target_url: str
    ) -> list[RuleFinding]:
        """Override to inspect Markdown or HTML link elements."""
        return []

    def visit_heading(
        self, file_path: Path, line_no: int, level: int, title: str
    ) -> list[RuleFinding]:
        """Override to inspect heading elements."""
        return []

    def visit_code_block(
        self, file_path: Path, start_line: int, lang: str, code: str
    ) -> list[RuleFinding]:
        """Override to inspect code blocks."""
        return []

    def _is_method_overridden(self, method_name: str) -> bool:
        method = getattr(self.__class__, method_name, None)
        base_method = getattr(ZenzicRuleV3, method_name, None)
        return method is not None and method is not base_method

    def _execute_ast_visitors(
        self, file_path: Path, text: str, findings: list[RuleFinding]
    ) -> None:
        if self._is_method_overridden("visit_link"):
            from zenzic.core.validator import PolyglotExtractor

            extractor = PolyglotExtractor()
            for link in extractor.extract_all_links(text):
                res = self.visit_link(file_path, link.line_no, link.raw_text, link.url)
                if res:
                    findings.extend(res)

        if self._is_method_overridden("visit_heading"):
            from zenzic.core.parser import parse

            with contextlib.suppress(Exception):
                doc = parse(text)
                self._walk_headings(doc, file_path, findings)

        if self._is_method_overridden("visit_code_block"):
            for start_line, lang, code in self._extract_code_blocks(text):
                res = self.visit_code_block(file_path, start_line, lang, code)
                if res:
                    findings.extend(res)

    def _extract_code_blocks(self, text: str) -> list[tuple[int, str, str]]:
        """Yield ``(start_line, lang, code)`` for every fenced code block.

        Mirrors the fence-matching logic in
        :class:`zenzic.core.rules.UntaggedCodeBlockRule` (``_FENCE_OPEN_RE``)
        so both stay in sync on what counts as an opening/closing fence.
        """
        from zenzic.core.rules import _FENCE_OPEN_RE

        blocks: list[tuple[int, str, str]] = []
        inside = False
        open_char = ""
        open_count = 0
        start_line = 0
        lang = ""
        code_lines: list[str] = []

        for line_no, line in enumerate(text.splitlines(), start=1):
            m = _FENCE_OPEN_RE.match(line)
            if not inside:
                if m:
                    fence = m.group("fence")
                    info = m.group("info").strip()
                    inside = True
                    open_char = fence[0]
                    open_count = len(fence)
                    start_line = line_no
                    lang = info.split()[0] if info else ""
                    code_lines = []
            else:
                if m:
                    fence = m.group("fence")
                    info = m.group("info").strip()
                    if fence[0] == open_char and len(fence) >= open_count and not info:
                        blocks.append((start_line, lang, "\n".join(code_lines)))
                        inside = False
                        open_char = ""
                        open_count = 0
                        continue
                code_lines.append(line)

        return blocks

    def _walk_headings(self, node: Any, file_path: Path, findings: list[RuleFinding]) -> None:
        from zenzic.core.ast import Heading, TextNode

        if isinstance(node, Heading) and self._is_method_overridden("visit_heading"):
            title = "".join(
                child.text for child in getattr(node, "children", []) if isinstance(child, TextNode)
            ).strip()
            line_no = getattr(node, "line_no", 1)
            res = self.visit_heading(file_path, line_no, node.level, title)
            if res:
                findings.extend(res)

        if hasattr(node, "children") and isinstance(node.children, list | tuple):
            for child in node.children:
                self._walk_headings(child, file_path, findings)
