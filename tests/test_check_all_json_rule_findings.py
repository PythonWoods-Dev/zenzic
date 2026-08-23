# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``check all --format json``'s ``references`` field must include
rule-engine findings (Z1xx-Z6xx), not just reference-pipeline findings.

Regression for: ``_output_check_all_json_findings`` (``_shared.py``) built
``references`` by iterating ``IntegrityReport.findings`` only — but
rule-engine output (AST/content/editorial rules, e.g. Z502 SHORT_CONTENT,
Z512 HEADING_SECTION_EMPTY) is written to a separate attribute,
``IntegrityReport.rule_findings``, never read by this function. The JSON
payload's ``references`` array was therefore always missing any rule-engine
finding, even when the same scan's text-mode output correctly reported it —
confirmed via direct comparison during `V031_SINGLE_FILE_PARSING_COST_BLOCKING`
(2026-08-23). Note: `zenzic-mcp` does NOT consume this payload — its
`check_document` tool is deliberately built against
`zenzic.core.incremental.IncrementalAnalysisEngine` instead, precisely to
avoid depending on this CLI-private JSON shape. The real consumers of this
field are external CI integrations and third-party tooling that invoke
`zenzic check all --format json` directly.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import jsonschema
import pytest
from typer.testing import CliRunner

from zenzic.main import app


runner = CliRunner()


@pytest.fixture
def short_page_sandbox(tmp_path: Path) -> Path:
    toml = tmp_path / ".zenzic.toml"
    toml.write_text(
        textwrap.dedent("""\
            docs_dir = "docs"

            [build_context]
            engine = "standalone"
        """),
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "short.md").write_text(
        textwrap.dedent("""\
            # Too Short

            Only a few words here.
        """),
        encoding="utf-8",
    )
    return tmp_path


def test_json_references_includes_rule_engine_findings(
    short_page_sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A genuine Z502 (rule-engine-only finding) must appear in the JSON
    payload's `references` array, matching what text-mode output reports."""
    monkeypatch.chdir(short_page_sandbox)

    result = runner.invoke(app, ["check", "all", "--format", "json"])

    payload = json.loads(result.stdout)
    assert any("Z502" in entry for entry in payload["references"]), (
        f"docs/short.md is genuinely short and text-mode output correctly "
        f"reports Z502 for it, but the JSON payload's `references` field "
        f"does not include it — rule-engine findings are being silently "
        f"dropped from this field. Full payload: {payload}"
    )


@pytest.fixture
def dead_reference_sandbox(tmp_path: Path) -> Path:
    """A page with a Z302 DEAD_DEF (warning-level ReferenceFinding, not a
    rule-engine finding) — verifies the pre-existing `not f.is_warning`
    filter removal, distinct from the rule_findings fix above."""
    toml = tmp_path / ".zenzic.toml"
    toml.write_text(
        textwrap.dedent("""\
            docs_dir = "docs"

            [build_context]
            engine = "standalone"
        """),
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "orphan-def.md").write_text(
        textwrap.dedent("""\
            # Orphan Definition Page

            This page defines a reference that is never used anywhere in its
            own body, which is exactly enough genuine prose to clear the
            short-content threshold on its own merits.

            [unused]: https://example.com/never-referenced
        """),
        encoding="utf-8",
    )
    return tmp_path


def test_json_references_includes_warning_level_reference_findings(
    dead_reference_sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A warning-level ReferenceFinding (Z302 DEAD_DEF) must appear in the
    JSON payload's `references` array — previously filtered out by a
    `not f.is_warning` check that made this field inconsistent with itself
    once rule-engine warnings (e.g. Z502) started being included."""
    monkeypatch.chdir(dead_reference_sandbox)

    result = runner.invoke(app, ["check", "all", "--format", "json"])

    payload = json.loads(result.stdout)
    assert any("Z302" in entry for entry in payload["references"]), (
        f"docs/orphan-def.md defines an unused reference and text-mode "
        f"output correctly reports Z302 (a warning) for it, but the JSON "
        f"payload's `references` field does not include it. Full payload: "
        f"{payload}"
    )


def test_json_references_with_rule_findings_still_matches_output_schema(
    short_page_sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The enriched `references` array (now containing rule-engine findings)
    must still validate against the public zenzic-output.schema.json contract."""
    monkeypatch.chdir(short_page_sandbox)

    result = runner.invoke(app, ["check", "all", "--format", "json"])
    payload = json.loads(result.stdout)

    repo_root = Path(__file__).resolve().parent.parent
    schema_path = repo_root / "zenzic-output.schema.json"
    with open(schema_path) as f:
        schema = json.load(f)

    jsonschema.validate(instance=payload, schema=schema)
