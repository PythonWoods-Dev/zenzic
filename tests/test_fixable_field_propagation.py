# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""TDD coverage for V031_FIXABLE_FIELD_EXPANSION_RULE17_CHECKLIST_AND_CLI_RENAME_FEATURE
Phase 1: the `fixable` field added to --format json, SARIF, and `zenzic inspect codes`,
derived from the same CODE_DEFINITIONS registry `zenzic explain` already reads --no new
registry, no duplicated data.
"""

from __future__ import annotations

import json

import pytest


class TestJSONFindingsFixableField:
    def test_fixable_code_shows_true(self, capsys: pytest.CaptureFixture[str]) -> None:
        from zenzic.cli._shared import _output_json_findings
        from zenzic.core.reporter import Finding

        findings = [
            Finding(
                rel_path="docs/index.md",
                line_no=5,
                code="Z515",  # BARE_URL_USED, fixable=True
                severity="warning",
                message="Bare URL used",
            )
        ]
        _output_json_findings(findings, elapsed=0.1)
        data = json.loads(capsys.readouterr().out)
        assert data["findings"][0]["fixable"] is True

    def test_non_fixable_code_shows_false(self, capsys: pytest.CaptureFixture[str]) -> None:
        from zenzic.cli._shared import _output_json_findings
        from zenzic.core.reporter import Finding

        findings = [
            Finding(
                rel_path="docs/index.md",
                line_no=5,
                code="Z101",  # LINK_BROKEN, fixable=False
                severity="error",
                message="Broken link",
            )
        ]
        _output_json_findings(findings, elapsed=0.1)
        data = json.loads(capsys.readouterr().out)
        assert data["findings"][0]["fixable"] is False


class TestSARIFFixableProperty:
    def test_fixable_code_rule_descriptor_shows_true(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from zenzic.cli._shared import _output_sarif_findings
        from zenzic.core.reporter import Finding

        findings = [
            Finding(
                rel_path="docs/index.md",
                line_no=1,
                code="Z517",  # HEADING_PUNCTUATION, fixable=True
                severity="warning",
                message="Trailing punctuation",
            )
        ]
        _output_sarif_findings(findings, version="0.31.0")
        data = json.loads(capsys.readouterr().out)
        rule = next(r for r in data["runs"][0]["tool"]["driver"]["rules"] if r["id"] == "Z517")
        assert rule["properties"]["fixable"] is True

    def test_non_fixable_code_rule_descriptor_shows_false(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from zenzic.cli._shared import _output_sarif_findings
        from zenzic.core.reporter import Finding

        findings = [
            Finding(
                rel_path="docs/index.md",
                line_no=1,
                code="Z101",  # LINK_BROKEN, fixable=False
                severity="error",
                message="Broken link",
            )
        ]
        _output_sarif_findings(findings, version="0.31.0")
        data = json.loads(capsys.readouterr().out)
        rule = next(r for r in data["runs"][0]["tool"]["driver"]["rules"] if r["id"] == "Z101")
        assert rule["properties"]["fixable"] is False

    def test_custom_rule_rule_descriptor_shows_false(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A ZZ- custom rule (no CODE_DEFINITIONS entry) is never auto-fixable."""
        from zenzic.cli._shared import _output_sarif_findings
        from zenzic.core.reporter import Finding

        findings = [
            Finding(
                rel_path="docs/index.md",
                line_no=1,
                code="ZZ-CUSTOM",
                severity="warning",
                message="Custom rule violation",
            )
        ]
        _output_sarif_findings(findings, version="0.31.0")
        data = json.loads(capsys.readouterr().out)
        rule = next(r for r in data["runs"][0]["tool"]["driver"]["rules"] if r["id"] == "ZZ-CUSTOM")
        assert rule["properties"]["fixable"] is False
