# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Contract tests for the Zenzic code registry stability.

These tests enforce the FROZEN_CODES contract: codes that can NEVER be
renumbered, removed, or have their description/severity changed.

Any mutation of a frozen code's metadata must fail this test immediately.
This is the enforcement mechanism for the ADR-012 stability contract.
"""

from zenzic.core.codes import (
    CODE_DESCRIPTIONS,
    CODE_NAMES,
    CODE_SARIF_LEVELS,
    FROZEN_CODES,
    NON_SUPPRESSIBLE_CODES,
    PLUGIN_FORBIDDEN_EXITS,
)


class TestFrozenCodesContract:
    """Verify that all FROZEN_CODES are present and immutable."""

    def test_frozen_codes_exist_in_registry(self) -> None:
        """All codes in FROZEN_CODES must be registered in CODE_NAMES."""
        missing = FROZEN_CODES - set(CODE_NAMES.keys())
        assert not missing, f"FROZEN_CODES contains codes not in CODE_NAMES: {missing}"

    def test_frozen_codes_have_descriptions(self) -> None:
        """All codes in FROZEN_CODES must have descriptions in CODE_DESCRIPTIONS."""
        missing = FROZEN_CODES - set(CODE_DESCRIPTIONS.keys())
        assert not missing, f"FROZEN_CODES missing descriptions: {missing}"

    def test_frozen_codes_have_sarif_levels(self) -> None:
        """All codes in FROZEN_CODES must have SARIF levels in CODE_SARIF_LEVELS."""
        missing = FROZEN_CODES - set(CODE_SARIF_LEVELS.keys())
        assert not missing, f"FROZEN_CODES missing SARIF levels: {missing}"

    def test_frozen_codes_metadata_snapshot(self) -> None:
        """Golden snapshot: frozen code metadata must match expected values.

        If this test fails, you have mutated a frozen code's description or severity.
        This is NOT allowed without Architecture Council approval and a major version bump.
        """
        # Golden file: expected metadata for each frozen code.
        # Any change here MUST be approved by the Architecture Council and documented
        # in ADR amendments and RELEASE.md.
        golden_snapshot: dict[str, dict[str, str]] = {
            "Z201": {
                "name": "CREDENTIAL_SECRET",
                "description": "Potential credential or secret detected in documentation content",
                "sarif_level": "error",
            },
            "Z202": {
                "name": "PATH_TRAVERSAL",
                "description": "Link escapes the documentation root boundary (path traversal)",
                "sarif_level": "error",
            },
            "Z203": {
                "name": "PATH_TRAVERSAL_FATAL",
                "description": "Path traversal targeting OS system directories — fatal security breach",
                "sarif_level": "error",
            },
            "Z204": {
                "name": "FORBIDDEN_TERM",
                "description": "Forbidden project term detected in documentation content",
                "sarif_level": "error",
            },
            "Z405": {
                "name": "UNUSED_ASSET",
                "description": "Asset file not referenced by any documentation page",
                "sarif_level": "warning",
            },
            "Z406": {
                "name": "NAV_CONTRACT",
                "description": "Navigation contract violation detected",
                "sarif_level": "warning",
            },
            "Z601": {
                "name": "BRAND_OBSOLESCENCE",
                "description": "Deprecated brand term found in documentation source",
                "sarif_level": "warning",
            },
        }

        for code, expected_meta in golden_snapshot.items():
            actual_name = CODE_NAMES.get(code)
            actual_description = CODE_DESCRIPTIONS.get(code)
            actual_sarif = CODE_SARIF_LEVELS.get(code)

            assert actual_name == expected_meta["name"], (
                f"{code} name mismatch: expected {expected_meta['name']!r}, got {actual_name!r}"
            )
            assert actual_description == expected_meta["description"], (
                f"{code} description mismatch: expected {expected_meta['description']!r}, got {actual_description!r}"
            )
            assert actual_sarif == expected_meta["sarif_level"], (
                f"{code} SARIF level mismatch: expected {expected_meta['sarif_level']!r}, got {actual_sarif!r}"
            )


class TestNonSuppressibleCodesContract:
    """Verify the NON_SUPPRESSIBLE_CODES stability contract."""

    def test_non_suppressible_codes_are_frozen(self) -> None:
        """All NON_SUPPRESSIBLE_CODES must be in FROZEN_CODES."""
        not_frozen = NON_SUPPRESSIBLE_CODES - FROZEN_CODES
        assert not not_frozen, f"NON_SUPPRESSIBLE_CODES not in FROZEN_CODES: {not_frozen}"

    def test_non_suppressible_contains_credential_and_traversal(self) -> None:
        """Credential scanner (Z201, Z204) and path traversal guard (Z202, Z203) must be non-suppressible."""
        required = {"Z201", "Z202", "Z203", "Z204"}
        missing = required - NON_SUPPRESSIBLE_CODES
        assert not missing, f"Required non-suppressible codes missing: {missing}"


class TestPluginForbiddenExitsContract:
    """Verify the PLUGIN_FORBIDDEN_EXITS stability contract."""

    def test_plugin_forbidden_exits_contains_credential_and_traversal(self) -> None:
        """Exit codes 2 (credential scanner) and 3 (path traversal guard) must be forbidden for plugins."""
        assert 2 in PLUGIN_FORBIDDEN_EXITS, (
            "Exit 2 (credential scanner) must be forbidden for plugins"
        )
        assert 3 in PLUGIN_FORBIDDEN_EXITS, (
            "Exit 3 (path traversal guard) must be forbidden for plugins"
        )

    def test_plugin_forbidden_exits_is_immutable(self) -> None:
        """PLUGIN_FORBIDDEN_EXITS must be a frozenset."""
        assert isinstance(PLUGIN_FORBIDDEN_EXITS, frozenset), (
            "PLUGIN_FORBIDDEN_EXITS must be frozenset"
        )
