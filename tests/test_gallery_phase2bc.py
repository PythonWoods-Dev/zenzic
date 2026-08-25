# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Gallery integration tests — Phase 2B/2C atomic coverage units.

Covers the five new example fixtures and their expected behaviour:

    Z104  FILE_NOT_FOUND           — link target missing from filesystem
    Z107  CIRCULAR_ANCHOR          — self-referential anchor link
    Z401  MISSING_DIRECTORY_INDEX  — directory has docs but no index page
    Z404  CONFIG_ASSET_MISSING     — engine config references a missing asset
    Z406  NAV_CONTRACT             — extra.alternate link absent from VSM
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _helpers import make_mgr

from zenzic.cli._check import _collect_all_results, _to_findings
from zenzic.cli._lab import _GALLERY, _examples_root
from zenzic.models.config import ZenzicConfig


# ── Helpers ───────────────────────────────────────────────────────────────────


def _examples() -> Path:
    return _examples_root()


def _run(code: str) -> tuple[list, int, int]:  # type: ignore[type-arg]
    """Return (findings, errors, warnings) for a gallery act.

    Runs the act through the same path as ``zenzic lab <code>`` but
    captures the reporter output silently.
    """
    act = _GALLERY[code]
    example_dir = _examples() / act.example_dir
    config, _ = ZenzicConfig.load(example_dir)
    docs_root = (example_dir / config.docs_dir).resolve()
    mgr = make_mgr(config, repo_root=example_dir, docs_root=docs_root)
    results = _collect_all_results(example_dir, docs_root, config, mgr, strict=False)
    findings = _to_findings(results, docs_root, repo_root=example_dir)
    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")
    return findings, errors, warnings


# ── _GALLERY registration ─────────────────────────────────────────────────────


def test_z104_registered_in_gallery() -> None:
    assert "z104" in _GALLERY


def test_z107_registered_in_gallery() -> None:
    assert "z107" in _GALLERY


def test_z401_registered_in_gallery() -> None:
    assert "z401" in _GALLERY


def test_z404_registered_in_gallery() -> None:
    assert "z404" in _GALLERY


def test_z406_registered_in_gallery() -> None:
    assert "z406" in _GALLERY


def test_z410_registered_in_gallery() -> None:
    assert "z410" in _GALLERY


def test_z411_registered_in_gallery() -> None:
    assert "z411" in _GALLERY


def test_z610_registered_in_gallery() -> None:
    assert "z610" in _GALLERY


def test_z611_registered_in_gallery() -> None:
    assert "z611" in _GALLERY


def test_all_active_codes_covered_in_gallery() -> None:
    from zenzic.core.codes import CODE_DEFINITIONS

    # Non-scannable internal, governance, or system escalation codes
    INTERNAL_CODES = {
        "z000",
        "z106",
        "z111",
        "z112",
        "z113",
        "z114",
        "z203",
        "z504",
        "z506",
        "z901",
        "z902",
        "z906",
    }

    active_codes = {code.lower() for code in CODE_DEFINITIONS if code.lower() not in INTERNAL_CODES}
    gallery_codes = set(_GALLERY.keys())
    missing = active_codes - gallery_codes
    assert not missing, f"Missing lab scenarios for active codes: {sorted(missing)}"


# ── Fixture directory existence ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "code,dirname",
    [
        ("z104", "z104-file-not-found"),
        ("z107", "z107-circular-anchor"),
        ("z401", "z401-missing-directory-index"),
        ("z404", "z404-config-asset-missing"),
        ("z406", "z406-nav-contract"),
        ("z410", "z410-unreachable-graph-node"),
        ("z411", "z411-dead-end-node"),
        ("z610", "z610-required-frontmatter"),
        ("z611", "z611-forbidden-domain"),
    ],
)
def test_fixture_directory_exists(code: str, dirname: str) -> None:
    assert (_examples() / dirname).is_dir()


# ── Z104 FILE_NOT_FOUND ───────────────────────────────────────────────────────


class TestZ104FileNotFound:
    def test_z104_produces_exactly_one_error(self) -> None:
        _, errors, warnings = _run("z104")
        assert errors == 1
        assert warnings == 0

    def test_z104_finding_code_is_z101(self) -> None:
        # Per CORE-REFACTOR-005, missing markdown link targets are uniformly Z101
        findings, _, _ = _run("z104")
        codes = [f.code for f in findings]
        assert "Z101" in codes

    def test_z104_finding_message_contains_missing_path(self) -> None:
        findings, _, _ = _run("z104")
        z101_msgs = [f.message for f in findings if f.code == "Z101"]
        assert any("api/reference.md" in m or "api/reference" in m for m in z101_msgs)

    def test_z104_expected_pass_false(self) -> None:
        assert _GALLERY["z104"].expected_pass is False


# ── Z107 CIRCULAR_ANCHOR ──────────────────────────────────────────────────────


class TestZ107CircularAnchor:
    def test_z107_produces_exactly_one_warning(self) -> None:
        _, errors, warnings = _run("z107")
        assert errors == 0
        assert warnings == 1

    def test_z107_finding_code_is_z107(self) -> None:
        findings, _, _ = _run("z107")
        codes = [f.code for f in findings]
        assert "Z107" in codes

    def test_z107_finding_mentions_setup_fragment(self) -> None:
        findings, _, _ = _run("z107")
        z107_msgs = [f.message for f in findings if f.code == "Z107"]
        assert any("#setup" in m.lower() or "setup" in m.lower() for m in z107_msgs)

    def test_z107_expected_pass_false(self) -> None:
        """Z107 is a warning — met_expectation uses errors>0 or warnings>0."""
        assert _GALLERY["z107"].expected_pass is False


# ── Z401 MISSING_DIRECTORY_INDEX ──────────────────────────────────────────────


class TestZ401MissingDirectoryIndex:
    def test_z401_produces_zero_errors_zero_warnings(self) -> None:
        _, errors, warnings = _run("z401")
        assert errors == 0
        assert warnings == 0

    def test_z401_produces_one_info_finding(self) -> None:
        findings, _, _ = _run("z401")
        info = [f for f in findings if f.code == "Z401"]
        assert len(info) == 1

    def test_z401_finding_mentions_guide_directory(self) -> None:
        findings, _, _ = _run("z401")
        z401_msgs = [f.message for f in findings if f.code == "Z401"]
        assert any("index" in m.lower() or "directory" in m.lower() for m in z401_msgs)

    def test_z401_expected_pass_true(self) -> None:
        assert _GALLERY["z401"].expected_pass is True

    def test_z401_show_info_true(self) -> None:
        assert _GALLERY["z401"].show_info is True


# ── Z404 CONFIG_ASSET_MISSING ─────────────────────────────────────────────────


class TestZ404ConfigAssetMissing:
    def test_z404_produces_zero_errors_one_warning(self) -> None:
        _, errors, warnings = _run("z404")
        assert errors == 0
        assert warnings == 1

    def test_z404_finding_code_is_z404(self) -> None:
        findings, _, _ = _run("z404")
        codes = [f.code for f in findings]
        assert "Z404" in codes

    def test_z404_finding_mentions_logo_asset(self) -> None:
        findings, _, _ = _run("z404")
        z404_msgs = [f.message for f in findings if f.code == "Z404"]
        assert any("logo" in m.lower() for m in z404_msgs)

    def test_z404_expected_pass_false(self) -> None:
        assert _GALLERY["z404"].expected_pass is False


# ── Z406 NAV_CONTRACT ─────────────────────────────────────────────────────────


class TestZ406NavContract:
    def test_z406_produces_exactly_one_warning(self) -> None:
        # Z406 is "warning" per codes.py's CODE_DEFINITIONS (the SSoT). This
        # test used to assert errors==1, warnings==0, locking in a bug where
        # _check.py hardcoded severity="error" for Z406 instead of deriving
        # it via _finding_severity() -- fixed in
        # V031_Z406_SEVERITY_FIX_AND_SYSTEMIC_SWEEP (same bug shape as Z301).
        _, errors, warnings = _run("z406")
        assert errors == 0
        assert warnings == 1

    def test_z406_finding_code_is_z406(self) -> None:
        findings, _, _ = _run("z406")
        codes = [f.code for f in findings]
        assert "Z406" in codes

    def test_z406_finding_mentions_it_route(self) -> None:
        findings, _, _ = _run("z406")
        z406_msgs = [f.message for f in findings if f.code == "Z406"]
        assert any("/it/" in m for m in z406_msgs)

    def test_z406_expected_pass_false(self) -> None:
        assert _GALLERY["z406"].expected_pass is False


# ── Cross-cutting: engine routing ─────────────────────────────────────────────


def test_z104_uses_standalone_engine() -> None:
    act = _GALLERY["z104"]
    example_dir = _examples() / act.example_dir
    config, _ = ZenzicConfig.load(example_dir)
    assert config.build_context.engine == "standalone"


def test_z107_uses_standalone_engine() -> None:
    act = _GALLERY["z107"]
    example_dir = _examples() / act.example_dir
    config, _ = ZenzicConfig.load(example_dir)
    assert config.build_context.engine == "standalone"


def test_z401_uses_zensical_engine() -> None:
    act = _GALLERY["z401"]
    example_dir = _examples() / act.example_dir
    config, _ = ZenzicConfig.load(example_dir)
    assert config.build_context.engine == "zensical"


def test_z404_uses_mkdocs_engine() -> None:
    act = _GALLERY["z404"]
    example_dir = _examples() / act.example_dir
    config, _ = ZenzicConfig.load(example_dir)
    assert config.build_context.engine == "mkdocs"


def test_z406_uses_mkdocs_engine() -> None:
    act = _GALLERY["z406"]
    example_dir = _examples() / act.example_dir
    config, _ = ZenzicConfig.load(example_dir)
    assert config.build_context.engine == "mkdocs"


# ── Z610 REQUIRED_FRONTMATTER_MISSING ─────────────────────────────────────────


class TestZ610RequiredFrontmatter:
    def test_z610_produces_warning(self) -> None:
        _, errors, warnings = _run("z610")
        assert warnings >= 1

    def test_z610_finding_code_is_z610(self) -> None:
        findings, _, _ = _run("z610")
        codes = [f.code for f in findings]
        assert "Z610" in codes

    def test_z610_expected_pass_false(self) -> None:
        assert _GALLERY["z610"].expected_pass is False


# ── Z611 FORBIDDEN_DOMAIN_REFERENCE ───────────────────────────────────────────


class TestZ611ForbiddenDomain:
    def test_z611_produces_warning(self) -> None:
        _, errors, warnings = _run("z611")
        assert warnings >= 1

    def test_z611_finding_code_is_z611(self) -> None:
        findings, _, _ = _run("z611")
        codes = [f.code for f in findings]
        assert "Z611" in codes

    def test_z611_expected_pass_false(self) -> None:
        assert _GALLERY["z611"].expected_pass is False
