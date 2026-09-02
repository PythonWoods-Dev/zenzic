# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``zenzic doctor``'s three repository-health checks.

Each is pure over a repo root plus a :class:`DoctorConfig`, reads only public
repository content, and returns findings rather than printing — the CLI owns
presentation and exit codes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zenzic.core.doctor import (
    check_adr_citations,
    check_redirects,
    next_adr_number,
    run_all,
    scaffold_adr,
)
from zenzic.models.config import DoctorConfig


def _vault(root: Path, *record_ids: str) -> None:
    vault = root / "docs/developers/explanation/adr-vault/records"
    vault.mkdir(parents=True, exist_ok=True)
    for rid in record_ids:
        (vault / f"adr-{rid.lower()}-example.md").write_text(f"# {rid}\n", encoding="utf-8")


def _src(root: Path, name: str, body: str) -> None:
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / name).write_text(body, encoding="utf-8")


class TestAdrCitations:
    def test_a_cited_record_that_exists_is_clean(self, tmp_path: Path) -> None:
        _vault(tmp_path, "012")
        _src(tmp_path, "a.py", "# see ADR-012 for the taxonomy\n")
        assert check_adr_citations(tmp_path, DoctorConfig()) == []

    def test_a_phantom_citation_is_reported_with_its_location(self, tmp_path: Path) -> None:
        _vault(tmp_path, "012")
        _src(tmp_path, "a.py", "# see ADR-999 for the taxonomy\n")
        findings = check_adr_citations(tmp_path, DoctorConfig())
        assert len(findings) == 1
        assert "ADR-999" in findings[0].message
        assert findings[0].location == "src/a.py"

    def test_citations_in_docs_are_scanned_too(self, tmp_path: Path) -> None:
        _vault(tmp_path, "012")
        (tmp_path / "docs").mkdir(exist_ok=True)
        (tmp_path / "docs/page.md").write_text("Per ADR-777 we do this.\n", encoding="utf-8")
        assert [f.message.split()[0] for f in check_adr_citations(tmp_path, DoctorConfig())] == [
            "ADR-777"
        ]

    def test_a_record_is_matched_by_its_title_when_the_filename_omits_the_number(
        self, tmp_path: Path
    ) -> None:
        """A record filed under a slug name still satisfies its citation.

        Reproduces the real vault state: records such as ``adr-regex-acl.md``
        title themselves ``# ADR 013`` but carry no number in the filename.
        Matching on the filename alone reported four such records as phantom
        while the decision they record was sitting in the vault, readable.
        """
        vault = tmp_path / "docs/developers/explanation/adr-vault/records"
        vault.mkdir(parents=True, exist_ok=True)
        (vault / "adr-regex-acl.md").write_text("# ADR 013\n\nRE2 only.\n", encoding="utf-8")
        _src(tmp_path, "a.py", "# All regex through the ACL (ADR-013).\n")

        assert check_adr_citations(tmp_path, DoctorConfig()) == []

    def test_a_phantom_is_still_reported_when_no_title_matches(self, tmp_path: Path) -> None:
        """Title matching must not turn the check into a rubber stamp."""
        vault = tmp_path / "docs/developers/explanation/adr-vault/records"
        vault.mkdir(parents=True, exist_ok=True)
        (vault / "adr-regex-acl.md").write_text("# ADR 013\n", encoding="utf-8")
        _src(tmp_path, "a.py", "see ADR-061\n")

        findings = check_adr_citations(tmp_path, DoctorConfig())
        assert [f.message.split()[0] for f in findings] == ["ADR-061"]

    def test_each_phantom_is_reported_once_however_often_cited(self, tmp_path: Path) -> None:
        _vault(tmp_path, "012")
        _src(tmp_path, "a.py", "ADR-999\nADR-999\n")
        _src(tmp_path, "b.py", "ADR-999\n")
        assert len(check_adr_citations(tmp_path, DoctorConfig())) == 1

    def test_a_missing_vault_is_reported_as_one_actionable_finding(self, tmp_path: Path) -> None:
        _src(tmp_path, "a.py", "# ADR-012\n")
        findings = check_adr_citations(tmp_path, DoctorConfig())
        assert len(findings) == 1
        assert "adr_vault_path" in findings[0].message

    def test_a_custom_citation_pattern_is_honoured(self, tmp_path: Path) -> None:
        vault = tmp_path / "decisions"
        vault.mkdir(parents=True)
        (vault / "rfc-0001-thing.md").write_text("# RFC-0001\n", encoding="utf-8")
        _src(tmp_path, "a.py", "# RFC-0001 and RFC-0002\n")
        config = DoctorConfig(adr_vault_path=Path("decisions"), adr_citation_pattern=r"RFC-\d{4}")
        findings = check_adr_citations(tmp_path, config)
        assert [f.message.split()[0] for f in findings] == ["RFC-0002"]


class TestRedirects:
    def test_absent_file_is_not_a_finding(self, tmp_path: Path) -> None:
        """Most projects have none; firing on all of them would be noise."""
        assert check_redirects(tmp_path, DoctorConfig()) == []

    def test_a_well_formed_file_is_clean(self, tmp_path: Path) -> None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs/_redirects").write_text("# header\n\n/old  /new  301\n", encoding="utf-8")
        config = DoctorConfig(redirects_expected_blanks=1)
        assert check_redirects(tmp_path, config) == []

    def test_wrong_field_count_is_reported_with_a_line_number(self, tmp_path: Path) -> None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs/_redirects").write_text("/only-one-field\n", encoding="utf-8")
        findings = check_redirects(tmp_path, DoctorConfig(redirects_expected_blanks=0))
        assert len(findings) == 1
        assert "expected 3 fields" in findings[0].message
        assert findings[0].location == "docs/_redirects:1"

    def test_a_source_without_a_leading_slash_is_reported(self, tmp_path: Path) -> None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs/_redirects").write_text("old  /new  301\n", encoding="utf-8")
        findings = check_redirects(tmp_path, DoctorConfig(redirects_expected_blanks=0))
        assert any("must start with '/'" in f.message for f in findings)

    def test_blank_line_drift_is_reported(self, tmp_path: Path) -> None:
        """The tripwire: an unexplained reshaping of the file."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs/_redirects").write_text("# h\n\n\n\n/a  /b  301\n", encoding="utf-8")
        findings = check_redirects(tmp_path, DoctorConfig(redirects_expected_blanks=1))
        assert any("blank-line count is 3" in f.message for f in findings)

    def test_the_blank_count_check_can_be_disabled(self, tmp_path: Path) -> None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs/_redirects").write_text("# h\n\n\n\n/a  /b  301\n", encoding="utf-8")
        assert check_redirects(tmp_path, DoctorConfig(redirects_expected_blanks=0)) == []


class TestRunAll:
    def test_returns_every_check_even_when_all_are_clean(self, tmp_path: Path) -> None:
        _vault(tmp_path, "012")
        results = run_all(tmp_path, DoctorConfig())
        assert set(results) == {"config-schema", "adr-citations", "redirects"}

    def test_a_clean_repository_produces_no_findings(self, tmp_path: Path) -> None:
        _vault(tmp_path, "012")
        _src(tmp_path, "a.py", "# ADR-012\n")
        assert all(v == [] for v in run_all(tmp_path, DoctorConfig()).values())


class TestAdrScaffold:
    """``zenzic adr new`` allocates a number and writes the 5-section skeleton."""

    def test_next_number_skips_gaps_rather_than_counting_records(self, tmp_path: Path) -> None:
        """The vault has real gaps; reusing an id would repoint existing citations."""
        _vault(tmp_path, "002", "012", "075")
        assert next_adr_number(tmp_path, DoctorConfig()) == 76

    def test_next_number_on_an_empty_vault_starts_at_one(self, tmp_path: Path) -> None:
        (tmp_path / "docs/developers/explanation/adr-vault/records").mkdir(parents=True)
        assert next_adr_number(tmp_path, DoctorConfig()) == 1

    def test_scaffold_writes_the_five_canonical_sections(self, tmp_path: Path) -> None:
        _vault(tmp_path, "012")
        created = scaffold_adr(tmp_path, DoctorConfig(), 13, "Adopt RE2 For Matching")
        body = created.read_text(encoding="utf-8")
        for section in (
            "## Context",
            "## Decision",
            "## Rationale",
            "## Invariants",
            "## Consequences",
        ):
            assert section in body, f"missing {section}"

    def test_scaffold_filename_and_title_derive_from_the_argument(self, tmp_path: Path) -> None:
        _vault(tmp_path, "012")
        created = scaffold_adr(tmp_path, DoctorConfig(), 13, "Adopt RE2 For Matching")
        assert created.name == "adr-013-adopt-re2-for-matching.md"
        assert "# ADR 013: Adopt RE2 For Matching" in created.read_text(encoding="utf-8")

    def test_scaffold_carries_the_spdx_header(self, tmp_path: Path) -> None:
        _vault(tmp_path, "012")
        created = scaffold_adr(tmp_path, DoctorConfig(), 13, "Thing")
        # Assembled rather than written literally: REUSE scans this file too, and a
        # contiguous tag here is read as a (malformed) licence expression for the test.
        tag = "SPDX-License-" + "Identifier: Apache-2.0"
        assert tag in created.read_text(encoding="utf-8")

    def test_scaffold_refuses_to_overwrite_an_existing_record(self, tmp_path: Path) -> None:
        _vault(tmp_path, "012")
        scaffold_adr(tmp_path, DoctorConfig(), 13, "First")
        with pytest.raises(FileExistsError):
            scaffold_adr(tmp_path, DoctorConfig(), 13, "Second")

    def test_a_scaffolded_record_satisfies_its_own_citation_check(self, tmp_path: Path) -> None:
        """End to end: create ADR-013, cite it, doctor stays clean."""
        _vault(tmp_path, "012")
        scaffold_adr(tmp_path, DoctorConfig(), 13, "Adopt RE2")
        _src(tmp_path, "a.py", "# per ADR-013\n")
        assert check_adr_citations(tmp_path, DoctorConfig()) == []
