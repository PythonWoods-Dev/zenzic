# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Example Custom Rule SDK v3 implementations."""

from __future__ import annotations

from pathlib import Path

from zenzic.core.rules import RuleFinding
from zenzic.models.rules import RuleMetadata
from zenzic.sdk.rules import ZenzicRuleV3


class NoTodoRule(ZenzicRuleV3):
    """SDK v3 custom rule that forbids the word 'TODO' in documentation lines."""

    metadata = RuleMetadata(
        code="ZZ-NO-TODO",
        title="Forbidden TODO Marker",
        description="TODO markers must not appear in published documentation.",
        severity="warning",
        category="content",
        penalty=1.0,
    )

    def visit_line(self, file_path: Path, line_no: int, line_text: str) -> list[RuleFinding]:
        if "TODO" in line_text:
            return [
                self.create_finding(
                    file_path=file_path,
                    line_no=line_no,
                    message="Forbidden TODO marker found in source line.",
                    matched_line=line_text,
                )
            ]
        return []
