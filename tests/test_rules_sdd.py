# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Test suite for Specification-Driven Development (SDD) rules: Z521, Z522, Z523, Z412."""

from pathlib import Path

from zenzic.core.content import (
    check_heading_order,
    check_required_table_columns,
    check_table_cell_enums,
)
from zenzic.core.governance import PolicyEvaluator
from zenzic.models.config import PoliciesConfig, ZenzicConfig
from zenzic.models.vsm import Route, VirtualSiteMap


DUMMY_FILE = Path("docs/specs/spec-01.md")


def test_z521_required_table_column() -> None:
    doc = "# API Reference\n\n| Endpoint | Method |\n| :--- | :--- |\n| /users | GET |\n"
    # Required columns across all tables: ["Endpoint", "Method", "Status"]
    req_cols = {"*": ["Endpoint", "Method", "Status"]}
    findings = check_required_table_columns(DUMMY_FILE, doc, req_cols)
    assert len(findings) == 1
    assert findings[0].rule_id == "Z521"
    assert findings[0].line_no == 3
    assert "Status" in findings[0].message


def test_z521_heading_context_filter() -> None:
    doc = (
        "# Overview\n\n"
        "| Name | Version |\n"
        "| --- | --- |\n"
        "| Zenzic | 0.31 |\n\n"
        "# Specs\n\n"
        "| Feature | Owner |\n"
        "| --- | --- |\n"
        "| SDD | PythonWoods |\n"
    )
    # Required only under Specs heading
    req_cols = {"^Specs$": ["Feature", "Owner", "Status"]}
    findings = check_required_table_columns(DUMMY_FILE, doc, req_cols)
    assert len(findings) == 1
    assert findings[0].rule_id == "Z521"
    assert findings[0].line_no == 9
    assert "Status" in findings[0].message


def test_z522_table_cell_enum() -> None:
    doc = (
        "# Status Table\n\n"
        "| Name | Status |\n"
        "| :--- | :---: |\n"
        "| Parser | `stable` |\n"
        "| Engine | unknown_status |\n"
        "| LSP | `review` |\n"
    )
    enums = {"Status": ["draft", "review", "stable"]}
    findings = check_table_cell_enums(DUMMY_FILE, doc, enums)
    assert len(findings) == 1
    assert findings[0].rule_id == "Z522"
    assert "unknown_status" in findings[0].message
    assert findings[0].line_no == 6


def test_z523_heading_order_violation() -> None:
    doc = "# API Reference\n\nDetails...\n\n# Overview\n\nIntroduction...\n"
    required_order = ["^Overview$", "^API Reference$"]
    findings = check_heading_order(DUMMY_FILE, doc, required_order)
    assert len(findings) == 1
    assert findings[0].rule_id == "Z523"
    assert "Overview" in findings[0].message


def test_policy_evaluator_integrates_sdd_rules() -> None:
    config = ZenzicConfig(
        policies=PoliciesConfig(
            required_table_columns={"*": ["ColA", "ColB"]},
            table_cell_enums={"ColA": ["valid1", "valid2"]},
            required_heading_order=["^First$", "^Second$"],
        )
    )
    evaluator = PolicyEvaluator(config)
    assert evaluator.is_active is True

    doc = "# Second\n\n| ColA |\n| --- |\n| invalid_val |\n\n# First\n"
    findings = evaluator.check(DUMMY_FILE, doc)
    rule_ids = {f.rule_id for f in findings}
    assert "Z521" in rule_ids  # Missing ColB
    assert "Z522" in rule_ids  # Invalid enum value
    assert "Z523" in rule_ids  # Out-of-order headings


def test_z412_traceability_detection() -> None:
    from zenzic.core.topology import detect_traceability_violations

    vsm = VirtualSiteMap()
    # Route for target spec
    vsm["/specs/sdd/"] = Route(url="/specs/sdd/", source="specs/sdd.md", status="REACHABLE")
    # Route for architecture doc
    vsm["/arch/overview/"] = Route(
        url="/arch/overview/", source="arch/overview.md", status="REACHABLE"
    )

    # Currently no incoming links to /specs/sdd/
    targets = {"specs/**": ["arch/**"]}
    violations = detect_traceability_violations(vsm, targets)
    assert len(violations) == 1
    assert violations[0][0] == "/specs/sdd/"

    # Now add incoming link from arch/overview.md
    vsm.incoming_links["/specs/sdd/"] = {Path("arch/overview.md")}
    violations = detect_traceability_violations(vsm, targets)
    assert len(violations) == 0
