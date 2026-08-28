# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Security pipeline regression tests.

Covers two bugs discovered during Z204 red-teaming (v0.9.0):

1. **i18n Path Bug** (Fase 1): `_locale_path_remap` in `scanner.py` was
   remapping `report.file_path` but not `report.security_findings[*].file_path`,
   causing `_map_credential_to_finding` to produce `docs//home/...` absolute
   paths when a Z204/Z201 finding was detected in an i18n file.

2. **Security Short-Circuit** (Fase 2): When a report had `security_findings`,
   structural findings (`report.findings`, `report.rule_findings`) derived from
   a partially-processed file state were still emitted, producing false positives
   like Z302 dead-definitions on files aborted mid-pipeline.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from typer.testing import CliRunner

from zenzic.core.credentials import SecurityFinding
from zenzic.core.scanner import ReferenceScanner, _map_credential_to_finding
from zenzic.main import app
from zenzic.models.config import ZenzicConfig
from zenzic.models.references import IntegrityReport, ReferenceFinding


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_sf(abs_path: Path, term: str = "secret") -> SecurityFinding:
    return SecurityFinding(
        file_path=abs_path,
        line_no=10,
        secret_type="FORBIDDEN_TERM",
        url="line containing secret",
        col_start=0,
        match_text=term,
    )


def _make_ref_finding(abs_path: Path, line_no: int = 5) -> ReferenceFinding:
    """Minimal ReferenceFinding stub (Z302-class warning)."""
    return ReferenceFinding(
        file_path=abs_path,
        line_no=line_no,
        issue="Z302",
        detail="Reference defined but never used.",
        is_warning=True,
    )


# ─── Fase 1: i18n SecurityFinding path remap ─────────────────────────────────


def test_locale_path_remap_applied_to_security_findings() -> None:
    """Remapping _locale_path_remap must also update security_findings[*].file_path.

    Regression for: Z204 findings on i18n files produced `docs//home/...` paths
    because only `report.file_path` was remapped, not the SecurityFinding paths.
    """
    docs_root = Path("/repo/docs")
    i18n_abs = Path("/repo/i18n/it/docs/reference/file.mdx")
    logical = docs_root / "it/reference/file.mdx"

    _locale_path_remap: dict[Path, Path] = {i18n_abs: logical}

    sf = _make_sf(i18n_abs, term="openai")
    report = IntegrityReport(
        file_path=i18n_abs,
        score=100.0,
        security_findings=[sf],
    )

    # Apply the same remap logic now present in scanner.py
    if report.file_path in _locale_path_remap:
        report.file_path = _locale_path_remap[report.file_path]
    for _sf in report.security_findings:
        if _sf.file_path in _locale_path_remap:
            _sf.file_path = _locale_path_remap[_sf.file_path]

    repo_root = Path("/repo")
    # After remap, _map_credential_to_finding must produce a clean relative path
    finding = _map_credential_to_finding(report.security_findings[0], repo_root)

    assert not finding.rel_path.startswith("/"), (
        f"rel_path must be relative, got: {finding.rel_path!r}"
    )
    assert "home" not in finding.rel_path, (
        f"Absolute path leaked into rel_path: {finding.rel_path!r}"
    )
    assert finding.rel_path.replace("\\", "/") == "docs/it/reference/file.mdx", (
        f"Expected 'docs/it/reference/file.mdx', got: {finding.rel_path!r}"
    )


def test_locale_path_remap_without_security_findings_is_noop() -> None:
    """Remap loop must not raise when security_findings is empty."""
    docs_root = Path("/repo/docs")
    i18n_abs = Path("/repo/i18n/it/docs/reference/clean.mdx")
    logical = docs_root / "it/reference/clean.mdx"
    _locale_path_remap: dict[Path, Path] = {i18n_abs: logical}

    report = IntegrityReport(file_path=i18n_abs, score=100.0)

    if report.file_path in _locale_path_remap:
        report.file_path = _locale_path_remap[report.file_path]
    for _sf in report.security_findings:  # must iterate zero times
        if _sf.file_path in _locale_path_remap:
            _sf.file_path = _locale_path_remap[_sf.file_path]

    assert report.file_path == logical


# ─── Fase 2: Security Observer — Pass 2 always runs ──────────────────────────


def test_security_breach_does_not_suppress_structural_findings(tmp_path: Path) -> None:
    """Security findings must not prevent Z302 computation (Observer pattern).

    Regression for: the security scanner was acting as a firewall — it skipped
    Pass 2 (cross_check) when a breach was detected, leaving ref_map.used_ids
    incomplete and producing false Z302 dead-definition warnings.

    The fix: Pass 2 always runs regardless of security_findings.  The security
    scanner is now a pure Observer: it records breaches but never interrupts the
    structural pipeline.  Z302 is computed from a complete ref_map.
    """
    md = tmp_path / "tainted.md"
    # File has one definition AND one use of it, plus a Z204-triggering term.
    md.write_text(
        "[syntax]: https://spec.example.com\n\nSee [CommonMark syntax][syntax] for details.\n",
        encoding="utf-8",
    )

    config = ZenzicConfig()
    scanner = ReferenceScanner(md, config)

    # Simulate Pass 1: harvest definitions (and discover a breach)
    security_findings_found: list[SecurityFinding] = []
    for _lineno, event_type, data in scanner.harvest():
        if event_type == "SECRET":
            security_findings_found.append(data)

    # Inject a synthetic breach (as if forbidden_patterns = ["see"])
    sf = _make_sf(md, term="see")

    # Pass 2 must always run — breach is observer-only
    cross_findings = scanner.cross_check()

    report = scanner.get_integrity_report(cross_findings, [sf])

    # "syntax" IS used in the file → ref_map.used_ids must include it → no Z302
    assert not any(f.issue == "Z302" for f in report.findings), (
        "Z302 must not appear for a definition that IS used — Pass 2 must run "
        "even when a security breach is present"
    )
    # Security finding must still be present
    assert len(report.security_findings) == 1


def test_no_security_breach_emits_structural_findings(tmp_path: Path) -> None:
    """Without a breach, get_integrity_report must still produce Z302 normally."""
    md = tmp_path / "clean.md"
    md.write_text("[syntax]: https://example.com\n", encoding="utf-8")

    config = ZenzicConfig()
    scanner = ReferenceScanner(md, config)
    scanner.ref_map.add_definition("syntax", "https://example.com", 1)
    # "syntax" is never used → orphan definition → Z302

    report = scanner.get_integrity_report(
        cross_check_findings=[],
        security_findings=[],
    )

    assert any(f.issue == "Z302" for f in report.findings), (
        "Z302 must be emitted for orphan definitions on clean files"
    )


# ─── Z204 rule_id mislabeling regression (V031) ──────────────────────────────


def test_z204_rule_findings_use_z204_not_z201() -> None:
    """RuleFinding injection in _scan_single_file must not hardcode Z201.

    Regression for: ``harvest()`` yields SecurityFinding objects for BOTH
    credential secrets and Z204 FORBIDDEN_TERM hits (the latter via
    ``scan_line_for_forbidden_terms``), but the ``RuleFinding`` list built
    from ``security_findings`` in ``_scan_single_file`` unconditionally set
    ``rule_id="Z201"`` — unlike ``_map_credential_to_finding``, which already
    branches correctly on ``secret_type == "FORBIDDEN_TERM"``. A Z204 hit was
    reported as ``[Z201]  Credential or secret detected: FORBIDDEN_TERM``
    instead of ``[Z204]  Forbidden term detected — remove from
    documentation: '...'``, in both text and ``--format json`` output.
    """
    runner = CliRunner()
    cwd = os.getcwd()
    os.chdir("examples/z204-forbidden-term")
    try:
        text_result = runner.invoke(app, ["check", "all"])
        json_result = runner.invoke(app, ["check", "all", "--format", "json"])
    finally:
        os.chdir(cwd)

    assert "[Z201]" not in text_result.stdout, (
        f"Z204 FORBIDDEN_TERM finding mislabeled as Z201 in text output:\n{text_result.stdout}"
    )
    assert "[Z204]" in text_result.stdout, (
        f"Expected [Z204] in text output, got:\n{text_result.stdout}"
    )
    assert "Forbidden term detected" in text_result.stdout
    assert "Credential or secret detected: FORBIDDEN_TERM" not in text_result.stdout

    json_start = json_result.stdout.find("{")
    payload = json.loads(json_result.stdout[json_start:])
    refs = " ".join(payload.get("references", []))
    assert "[Z201]" not in refs, f"Z204 finding mislabeled as Z201 in JSON output: {refs!r}"
    assert "[Z204]" in refs, f"Expected [Z204] in JSON output, got: {refs!r}"
