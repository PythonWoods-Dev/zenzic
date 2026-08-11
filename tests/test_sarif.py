# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path

import jsonschema

from zenzic.cli._shared import Finding, _output_sarif_findings
from zenzic.sdk import ZenzicRuleV3, RuleMetadata


class CustomSarifTestRule(ZenzicRuleV3):
    metadata = RuleMetadata(
        code="ZZ-SARIF-TEST",
        title="SARIF Integration Test Rule",
        description="Rule to test SARIF metadata propagation.",
        severity="error",
        category="governance",
        penalty=5.0,
        docs_url="https://zenzic.dev/docs/rules/ZZ-SARIF-TEST",
    )


def test_sarif_enrichment_and_schema_validation(capsys) -> None:
    schema_path = Path("tests/fixtures/sarif-2.1.0-schema.json")
    with open(schema_path) as f:
        sarif_schema = json.load(f)

    findings = [
        Finding(
            rel_path="docs/index.md",
            line_no=10,
            code="Z101",
            severity="error",
            message="Broken link target",
        ),
        Finding(
            rel_path="docs/guide.md",
            line_no=5,
            code="ZZ-SARIF-TEST",
            severity="error",
            message="Custom SARIF error",
        ),
    ]

    rule_instance = CustomSarifTestRule()
    rules_map = {"ZZ-SARIF-TEST": rule_instance}

    _output_sarif_findings(findings, version="0.28.0", rules_map=rules_map)
    captured = capsys.readouterr()

    sarif_data = json.loads(captured.out)

    # 1. Validate against official OASIS SARIF v2.1.0 JSON Schema
    jsonschema.validate(instance=sarif_data, schema=sarif_schema)

    # 2. Assert enriched rules array
    rules = sarif_data["runs"][0]["tool"]["driver"]["rules"]
    assert len(rules) == 2

    # Rules must be sorted alphabetically by id
    z101_rule = rules[0]
    assert z101_rule["id"] == "Z101"
    assert z101_rule["name"] == "LinkBroken"
    assert z101_rule["helpUri"] == "https://zenzic.dev/docs/reference/finding-codes#z101"
    assert z101_rule["defaultConfiguration"]["level"] == "error"
    assert z101_rule["properties"]["category"] == "structural"
    assert z101_rule["properties"]["penalty"] == 8.0

    custom_rule = rules[1]
    assert custom_rule["id"] == "ZZ-SARIF-TEST"
    assert custom_rule["helpUri"] == "https://zenzic.dev/docs/rules/ZZ-SARIF-TEST"
    assert custom_rule["defaultConfiguration"]["level"] == "error"
    assert custom_rule["properties"]["category"] == "governance"
    assert custom_rule["properties"]["penalty"] == 5.0

    # 3. Assert results array determinism
    results = sarif_data["runs"][0]["results"]
    assert len(results) == 2
    assert results[0]["ruleId"] == "ZZ-SARIF-TEST"
    assert results[0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "docs/guide.md"
    assert results[1]["ruleId"] == "Z101"
    assert results[1]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "docs/index.md"
