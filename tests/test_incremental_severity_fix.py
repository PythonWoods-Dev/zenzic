# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Regression tests for V031_INCREMENTAL_PY_SEVERITY_AUDIT.

Exhaustive enumeration of incremental.py's ~17 hardcoded-severity
RuleFinding(...) construction sites (following the bounded 6-site sample
from the prior session, which had checked Z201/Z205/Z410/Z411/Z123 plus one
site it could not identify precisely) found three live mismatches against
codes.py's CODE_DEFINITIONS -- the same "hardcoded literal bypasses the
SSoT" bug shape already fixed twice this session in _check.py (Z406, Z503)
and rules.py (Z107, Z902):

- Z120 (UNKNOWN_HTML_ATTRIBUTE): codes.py says "warning", incremental.py
  hardcoded "error" (validator.py:794 equivalent construction site).
- Z122 (JUMP_LINK_DETECTED): codes.py says "warning", incremental.py
  hardcoded "error".
- Z503 (SNIPPET_ERROR, via check_snippet_content()'s SnippetError.code):
  codes.py says "warning", incremental.py hardcoded "error" -- this is
  incremental.py's own instance of the exact bug already fixed in
  _check.py's standalone `check snippets` subcommand.

These tests exercise IncrementalAnalysisEngine's public process_changes()
API (no internals reached directly) and assert the LSP-surfaced diagnostic
severity matches codes.py, not the hardcoded literal.
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core.adapters import get_adapter
from zenzic.core.codes import code_severity
from zenzic.core.incremental import IncrementalAnalysisEngine
from zenzic.core.scanner import _build_rule_engine
from zenzic.models.config import ZenzicConfig
from zenzic.models.diagnostics import Severity
from zenzic.models.vsm import VirtualBufferOverlay, VirtualSiteMap


def _make_engine(
    tmp_path: Path,
) -> tuple[IncrementalAnalysisEngine, VirtualSiteMap, VirtualBufferOverlay]:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(exist_ok=True)
    config = ZenzicConfig(docs_dir="docs")
    rule_engine = _build_rule_engine(config)
    assert rule_engine is not None
    adapter = get_adapter(config.build_context, docs_dir, tmp_path)
    vsm = VirtualSiteMap()
    overlay = VirtualBufferOverlay(vsm)
    engine = IncrementalAnalysisEngine(
        config=config,
        rule_engine=rule_engine,
        adapter=adapter,
        docs_root=docs_dir,
        repo_root=tmp_path,
    )
    return engine, vsm, overlay


_EXPECTED_SEVERITY = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFORMATION: "info",
}


def test_z120_unknown_attribute_severity_matches_codes_py(tmp_path: Path) -> None:
    """Z120 is codes.py-classified as warning; must not surface as error."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text('<a href="x.md" data-custom="1">link</a>', encoding="utf-8")

    engine, vsm, overlay = _make_engine(tmp_path)
    results = engine.process_changes(vsm, overlay)
    all_diags = [d for diags in results.values() for d in diags]

    z120 = [d for d in all_diags if d.code == "Z120"]
    assert z120, "Fixture must trigger Z120 (unknown HTML attribute)"
    assert code_severity("Z120") == "warning"
    for d in z120:
        assert _EXPECTED_SEVERITY[d.severity] == "warning", (
            f"Z120 diagnostic severity is {d.severity!r}, expected 'warning' "
            f"to match codes.py's CODE_DEFINITIONS['Z120']"
        )


def test_z122_jump_link_severity_matches_codes_py(tmp_path: Path) -> None:
    """Z122 is codes.py-classified as warning; must not surface as error."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text('<a href="#">jump</a>', encoding="utf-8")

    engine, vsm, overlay = _make_engine(tmp_path)
    results = engine.process_changes(vsm, overlay)
    all_diags = [d for diags in results.values() for d in diags]

    z122 = [d for d in all_diags if d.code == "Z122"]
    assert z122, "Fixture must trigger Z122 (jump link)"
    assert code_severity("Z122") == "warning"
    for d in z122:
        assert _EXPECTED_SEVERITY[d.severity] == "warning", (
            f"Z122 diagnostic severity is {d.severity!r}, expected 'warning' "
            f"to match codes.py's CODE_DEFINITIONS['Z122']"
        )


def test_z503_snippet_error_severity_matches_codes_py(tmp_path: Path) -> None:
    """Z503 is codes.py-classified as warning; must not surface as error."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text(
        "```python\ndef broken(:\n```\n",
        encoding="utf-8",
    )

    engine, vsm, overlay = _make_engine(tmp_path)
    results = engine.process_changes(vsm, overlay)
    all_diags = [d for diags in results.values() for d in diags]

    z503 = [d for d in all_diags if d.code == "Z503"]
    assert z503, "Fixture must trigger Z503 (snippet syntax error)"
    assert code_severity("Z503") == "warning"
    for d in z503:
        assert _EXPECTED_SEVERITY[d.severity] == "warning", (
            f"Z503 diagnostic severity is {d.severity!r}, expected 'warning' "
            f"to match codes.py's CODE_DEFINITIONS['Z503']"
        )
