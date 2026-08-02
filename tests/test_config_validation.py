# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Unit and integration tests for Configuration Validation Engine (Z110, Z111)."""

from __future__ import annotations

from pathlib import Path

import pytest

from zenzic.core.incremental import IncrementalAnalysisEngine
from zenzic.core.scanner import scan_docs_references
from zenzic.models.config import ZenzicConfig, load_config_with_diagnostics
from zenzic.models.vsm import VirtualBufferOverlay, build_vsm


def test_z110_toml_syntax_error_line_extraction(tmp_path: Path) -> None:
    """Z110 extracts line numbers from TOML syntax errors in .zenzic.toml."""
    config_file = tmp_path / ".zenzic.toml"
    config_file.write_text(
        "[site]\n"
        "engine = 'standalone'\n"
        "placeholder_max_words = [ unclosed_array\n",  # line 3
        encoding="utf-8",
    )

    cfg, findings = load_config_with_diagnostics(tmp_path)
    assert cfg is None
    assert len(findings) == 1
    assert findings[0].code == "Z110"
    assert findings[0].severity == "error"
    assert findings[0].line_no in (3, 4)
    assert "TOML syntax error" in findings[0].message


def test_z111_schema_error_field_and_line_extraction(tmp_path: Path) -> None:
    """Z111 extracts field name and line number for Pydantic schema validation errors."""
    config_file = tmp_path / ".zenzic.toml"
    config_file.write_text(
        "placeholder_max_words = 'not_a_number'\n",  # line 1
        encoding="utf-8",
    )

    cfg, findings = load_config_with_diagnostics(tmp_path)
    assert cfg is None
    assert len(findings) >= 1
    z111 = next(f for f in findings if f.code == "Z111")
    assert z111.severity == "error"
    assert z111.line_no == 1
    assert "placeholder_max_words" in z111.message


def test_scanner_halts_markdown_analysis_on_config_error(tmp_path: Path) -> None:
    """Batch scanner halts Markdown scanning when Z110/Z111 exist."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Title\n\n[Broken Link](nonexistent.md)\n")

    (tmp_path / ".zenzic.toml").write_text("invalid_toml = [ missing_bracket\n")

    from zenzic.core.exclusion import LayeredExclusionManager

    excl = LayeredExclusionManager(ZenzicConfig(), repo_root=tmp_path, docs_root=docs)
    reports, _ = scan_docs_references(docs, excl, repo_root=tmp_path)
    assert len(reports) == 1
    assert len(reports[0].findings) == 1
    assert reports[0].findings[0].code == "Z110"


def test_incremental_engine_emits_config_diagnostic_without_crashing(tmp_path: Path) -> None:
    """LSP incremental engine converts config errors to ZenzicDiagnostic for .zenzic.toml."""
    docs = tmp_path / "docs"
    docs.mkdir()
    index_file = docs / "index.md"
    index_file.write_text("# Index\n")
    (tmp_path / ".zenzic.toml").write_text("placeholder_max_words = 'invalid'\n")

    from zenzic.core.adapters import StandaloneAdapter

    cfg = ZenzicConfig()
    adapter = StandaloneAdapter()
    engine = IncrementalAnalysisEngine(
        config=cfg,
        rule_engine=None,
        adapter=adapter,
        docs_root=docs,
        repo_root=tmp_path,
    )
    md_contents = {index_file.resolve(): "# Index\n"}
    vsm = build_vsm(adapter, docs, md_contents=md_contents)
    overlay = VirtualBufferOverlay(vsm)

    diags_map = engine.process_changes(vsm, overlay, changed_uris=None)
    config_uri = (tmp_path / ".zenzic.toml").resolve().as_uri()

    assert config_uri in diags_map
    diags = diags_map[config_uri]
    assert len(diags) >= 1
    assert diags[0].code == "Z111"


def test_dqs_score_collapses_to_zero_on_config_error() -> None:
    """Z110 and Z111 force DQS score to 0.0 with security_override = True."""
    from zenzic.core.scorer import compute_score

    report_z110 = compute_score({"Z110": 1})
    assert report_z110.score == 0
    assert report_z110.security_override is True

    report_z111 = compute_score({"Z111": 1})
    assert report_z111.score == 0
    assert report_z111.security_override is True


def test_local_config_validation(tmp_path: Path) -> None:
    """load_config_with_diagnostics validates .zenzic.local.toml and attaches finding to it."""
    (tmp_path / ".zenzic.toml").write_text("[build_context]\nengine = 'standalone'\n")
    (tmp_path / ".zenzic.local.toml").write_text("invalid_local_toml = [ unclosed_array\n")

    cfg, findings = load_config_with_diagnostics(tmp_path)
    assert cfg is None
    assert len(findings) == 1
    assert findings[0].code == "Z110"
    assert findings[0].rel_path == ".zenzic.local.toml"

