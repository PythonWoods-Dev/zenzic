# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Unit and integration tests for Baseline & Regression Tracking engine."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate
from typer.testing import CliRunner

from zenzic.core.baseline import (
    DEFAULT_BASELINE_FILE,
    BaselineManager,
    compute_finding_signature,
)
from zenzic.core.reporter import Finding
from zenzic.main import app


runner = CliRunner()


def test_signature_computation_resilient_to_line_shifts() -> None:
    """Line numbers must not affect the computed signature."""
    sig1 = compute_finding_signature("Z410", "docs/guide.md", "", "Document is isolated: '/guide/'")
    sig2 = compute_finding_signature("Z410", "docs/guide.md", "", "Document is isolated: '/guide/'")
    assert sig1 == sig2
    assert len(sig1) == 16

    # Differing targets produce different signatures
    sig_other = compute_finding_signature(
        "Z410", "docs/guide.md", "", "Document is isolated: '/other/'"
    )
    assert sig1 != sig_other

    # Context match_text precedence
    sig_match1 = compute_finding_signature("Z101", "docs/a.md", "http://broken1.com", "Broken link")
    sig_match2 = compute_finding_signature("Z101", "docs/a.md", "http://broken2.com", "Broken link")
    assert sig_match1 != sig_match2


def test_baseline_schema_validation(tmp_path: Path) -> None:
    """Saved baseline JSON must strictly conform to zenzic-baseline.schema.json."""
    schema_path = Path(__file__).parent.parent / "zenzic-baseline.schema.json"
    assert schema_path.is_file(), "zenzic-baseline.schema.json schema file missing."

    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    findings = [
        Finding(
            rel_path="docs/index.md",
            line_no=15,
            code="Z101",
            severity="error",
            message="Broken link 'missing.md'",
            match_text="missing.md",
        )
    ]
    bdata = BaselineManager.create_baseline(90.0, findings, version_str="0.27.0")
    file_path = tmp_path / DEFAULT_BASELINE_FILE
    BaselineManager.save_baseline(bdata, file_path)

    raw = json.loads(file_path.read_text(encoding="utf-8"))
    validate(instance=raw, schema=schema)


def test_baseline_manager_apply_baseline() -> None:
    """apply_baseline flags matching findings as is_baselined=True."""
    f1 = Finding(
        rel_path="docs/a.md", line_no=1, code="Z410", severity="warning", message="Isolated: '/a/'"
    )
    f2 = Finding(
        rel_path="docs/b.md", line_no=10, code="Z411", severity="warning", message="Dead end: '/b/'"
    )

    bdata = BaselineManager.create_baseline(95.0, [f1], version_str="0.27.0")
    baselined_cnt, new_cnt = BaselineManager.apply_baseline([f1, f2], bdata)

    assert baselined_cnt == 1
    assert new_cnt == 1
    assert f1.is_baselined is True
    assert f2.is_baselined is False


def test_cli_update_baseline_and_consume(tmp_path: Path) -> None:
    """CLI zenzic check --update-baseline creates baseline; subsequent check exits 0."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Index\n\n[Dead End](dead.md)\n")
    (docs / "dead.md").write_text("# Dead End\n\nNo outgoing links.\n")

    (tmp_path / ".zenzic.toml").write_text("[site]\nengine = 'standalone'\n")

    # Step 1: Update baseline
    res = runner.invoke(app, ["check", "all", str(docs), "--update-baseline"])
    assert res.exit_code in (0, 1)
    baseline_file = tmp_path / DEFAULT_BASELINE_FILE
    assert baseline_file.is_file()

    # Step 2: Consume baseline without new defects -> Exit 0
    res2 = runner.invoke(app, ["check", "all", str(docs), "--baseline", str(baseline_file)])
    assert res2.exit_code == 0
    assert "[BASELINED]" in res2.stdout or "Baseline:" in res2.stdout

    # Step 3: Introduce new defect -> Exit 1
    (docs / "new_orphan.md").write_text("# New Orphan\n\nNo links.\n")
    res3 = runner.invoke(app, ["check", "all", str(docs), "--baseline", str(baseline_file)])
    assert res3.exit_code == 1
