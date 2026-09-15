# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The ``[doctor]`` config section, and the boundary it must never cross.

``zenzic doctor``'s repository-health checks depend on conventions that are not
universal: where a project keeps its ADR records, how it cites them, where its
redirects file lives. Those cannot be hardcoded to Zenzic's own layout and still
be useful to anyone else, so they are configuration.

The defaults are Zenzic's own real values, and every one of them points at
**public repository content**. `.claude/` is gitignored and absent from every
clone, so a shipped command cannot read it under any configuration — these tests
assert that boundary directly rather than trusting the default string to stay
correct.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from zenzic.models.config import DoctorConfig, ZenzicConfig


class TestDefaults:
    def test_defaults_match_zenzics_own_public_layout(self) -> None:
        cfg = DoctorConfig()
        assert cfg.adr_vault_path == Path("docs/developers/explanation/adr-vault")
        assert cfg.redirects_path == Path("docs/_redirects")
        assert cfg.adr_citation_pattern == r"ADR-\d{3}"
        assert cfg.redirects_expected_blanks == 8

    def test_section_is_present_and_optional_on_the_root_model(self) -> None:
        """A repo with no [doctor] block still gets a usable default."""
        cfg = ZenzicConfig(docs_dir=Path("docs"))
        assert isinstance(cfg.doctor, DoctorConfig)
        assert cfg.doctor.adr_vault_path == Path("docs/developers/explanation/adr-vault")


class TestPublicScopeOnly:
    """`.claude/` must be unreachable — it does not exist in a clone."""

    def test_no_default_points_into_a_gitignored_control_plane(self) -> None:
        cfg = DoctorConfig()
        for value in (cfg.adr_vault_path, cfg.redirects_path):
            parts = Path(value).parts
            assert ".claude" not in parts, f"{value} reaches into the gitignored control plane"
            assert ".human" not in parts, f"{value} reaches into gitignored private material"

    def test_defaults_are_repo_relative_not_absolute(self) -> None:
        """An absolute default would leak this developer's own filesystem layout."""
        cfg = DoctorConfig()
        assert not cfg.adr_vault_path.is_absolute()
        assert not cfg.redirects_path.is_absolute()

    @pytest.mark.parametrize("bad", [".claude", ".claude/state", "docs/../.claude"])
    def test_a_configured_path_into_the_control_plane_is_rejected(self, bad: str) -> None:
        """Not merely defaulted away from — refused, so it cannot be opted into."""
        with pytest.raises(ValidationError):
            DoctorConfig(adr_vault_path=Path(bad))


class TestOverrides:
    def test_every_field_is_overridable(self) -> None:
        cfg = DoctorConfig(
            adr_vault_path=Path("architecture/decisions"),
            adr_citation_pattern=r"RFC-\d{4}",
            redirects_path=Path("public/_redirects"),
            redirects_expected_blanks=0,
        )
        assert cfg.adr_vault_path == Path("architecture/decisions")
        assert cfg.adr_citation_pattern == r"RFC-\d{4}"
        assert cfg.redirects_path == Path("public/_redirects")
        assert cfg.redirects_expected_blanks == 0

    def test_a_negative_blank_line_expectation_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DoctorConfig(redirects_expected_blanks=-1)

    def test_an_uncompilable_citation_pattern_is_rejected_at_config_time(self) -> None:
        """Fail on load, not midway through a scan."""
        with pytest.raises(ValidationError):
            DoctorConfig(adr_citation_pattern="ADR-(unclosed")


class TestZenzicsOwnRepoNeedsNoConfig:
    def test_the_defaults_resolve_against_this_repository(self) -> None:
        """The acceptance criterion: zero explicit [doctor] config here."""
        repo_root = Path(__file__).resolve().parent.parent
        cfg = DoctorConfig()
        assert (repo_root / cfg.adr_vault_path).is_dir()
        assert (repo_root / cfg.redirects_path).is_file()
