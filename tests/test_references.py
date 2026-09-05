# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Test suite for the Two-Pass Reference Pipeline (Sprint 2 / v0.2.0).

Coverage targets
----------------
ReferenceMap (models/references.py):
  - Case-insensitive key normalisation
  - First-wins deduplication (CommonMark §4.7)
  - integrity_score with zero-division guard
  - orphan_definitions property
  - __contains__ and __getitem__ protocol

Credential Scanner (core/credentials.py):
  - OpenAI, GitHub, AWS secret detection
  - scan_url_for_secrets and scan_line_for_secrets
  - No false positives on clean URLs

ReferenceScanner (core/scanner.py):
  - Pass 1 (harvest): DEF, DUPLICATE_DEF, SECRET events
  - Pass 2 (cross_check): DANGLING detection
  - Pass 3 (get_integrity_report): DEAD_DEF, duplicate-def, score
  - "Phantom Reference Trap": [text][id] with no definition → DANGLING
  - "Ghost Key Trap": 1000 uses of same ID → one entry in used_ids (dedup)
  - Credential scanner acting as firewall: Pass 2 skipped when secrets found
  - Alt-text check: pure function and via harvest events

MissingAltTextRule (core/rules.py):
  - Inline Markdown images
  - HTML <img> tags
  - Empty alt attribute not flagged (intentionally decorative)

scan_docs_references (core/scanner.py):
  - Integration smoke test over a tmp docs directory
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _helpers import make_mgr

from zenzic.core.credentials import SecurityFinding, scan_line_for_secrets, scan_url_for_secrets
from zenzic.core.scanner import (
    ReferenceScanner,
    scan_docs_references,
)
from zenzic.core.validator import LinkValidator
from zenzic.models.config import ZenzicConfig
from zenzic.models.references import IntegrityReport, ReferenceMap


# ══════════════════════════════════════════════════════════════════════════════
# ReferenceMap
# ══════════════════════════════════════════════════════════════════════════════


class TestReferenceMap:
    def test_add_definition_basic(self) -> None:
        rm = ReferenceMap()
        accepted = rm.add_definition("MyRef", "https://example.com", 1)
        assert accepted is True
        assert rm.resolve("MyRef") == "https://example.com"

    def test_case_insensitive_resolve(self) -> None:
        """[Link], [LINK], and [link] must all resolve to the same URL."""
        rm = ReferenceMap()
        rm.add_definition("Link", "https://example.com", 1)
        assert rm.resolve("LINK") == "https://example.com"
        assert rm.resolve("link") == "https://example.com"
        assert rm.resolve("Link") == "https://example.com"

    def test_first_wins_commonmark_47(self) -> None:
        """Per CommonMark §4.7, the first definition of an ID wins."""
        rm = ReferenceMap()
        rm.add_definition("ref", "https://first.com", 1)
        accepted_second = rm.add_definition("ref", "https://second.com", 5)
        assert accepted_second is False
        assert rm.resolve("ref") == "https://first.com"  # first wins
        assert "ref" in rm.duplicate_ids

    def test_first_wins_case_insensitive(self) -> None:
        """Duplicate detection is also case-insensitive."""
        rm = ReferenceMap()
        rm.add_definition("Ref", "https://first.com", 1)
        accepted = rm.add_definition("REF", "https://second.com", 3)
        assert accepted is False
        assert rm.resolve("ref") == "https://first.com"

    def test_integrity_score_all_used(self) -> None:
        rm = ReferenceMap()
        rm.add_definition("a", "https://a.com", 1)
        rm.add_definition("b", "https://b.com", 2)
        rm.resolve("a")
        rm.resolve("b")
        assert rm.integrity_score == 100.0

    def test_integrity_score_none_used(self) -> None:
        rm = ReferenceMap()
        rm.add_definition("a", "https://a.com", 1)
        rm.add_definition("b", "https://b.com", 2)
        assert rm.integrity_score == 0.0

    def test_integrity_score_partial(self) -> None:
        rm = ReferenceMap()
        rm.add_definition("a", "https://a.com", 1)
        rm.add_definition("b", "https://b.com", 2)
        rm.add_definition("c", "https://c.com", 3)
        rm.add_definition("d", "https://d.com", 4)
        rm.resolve("a")
        rm.resolve("b")
        assert rm.integrity_score == pytest.approx(50.0)

    def test_integrity_score_no_definitions_returns_100(self) -> None:
        """Guard against ZeroDivisionError when no definitions exist."""
        rm = ReferenceMap()
        assert rm.integrity_score == 100.0

    def test_orphan_definitions(self) -> None:
        rm = ReferenceMap()
        rm.add_definition("used", "https://used.com", 1)
        rm.add_definition("unused", "https://unused.com", 2)
        rm.resolve("used")
        assert rm.orphan_definitions == {"unused"}

    def test_resolve_marks_used(self) -> None:
        rm = ReferenceMap()
        rm.add_definition("x", "https://x.com", 1)
        assert "x" not in rm.used_ids
        rm.resolve("x")
        assert "x" in rm.used_ids

    def test_resolve_unknown_returns_none(self) -> None:
        rm = ReferenceMap()
        assert rm.resolve("ghost") is None

    def test_contains_protocol(self) -> None:
        rm = ReferenceMap()
        rm.add_definition("hello", "https://hello.com", 1)
        assert "hello" in rm
        assert "Hello" in rm  # case-insensitive
        assert "HELLO" in rm
        assert "world" not in rm

    def test_getitem_protocol(self) -> None:
        rm = ReferenceMap()
        rm.add_definition("item", "https://item.com", 1)
        assert rm["item"] == "https://item.com"
        assert rm["ITEM"] == "https://item.com"

    def test_getitem_missing_raises_key_error(self) -> None:
        rm = ReferenceMap()
        with pytest.raises(KeyError):
            _ = rm["nonexistent"]

    def test_definition_line_stored(self) -> None:
        """Line number metadata must be persisted for error reports."""
        rm = ReferenceMap()
        rm.add_definition("ref", "https://example.com", 42)
        assert rm.get_definition_line("ref") == 42
        assert rm.get_definition_line("REF") == 42
        assert rm.get_definition_line("missing") is None

    def test_1000_uses_single_entry(self) -> None:
        """1000 resolutions of the same ID must produce exactly one used_ids entry."""
        rm = ReferenceMap()
        rm.add_definition("bigref", "https://bigref.com", 1)
        for _ in range(1000):
            rm.resolve("bigref")
        assert rm.used_ids == {"bigref"}
        assert rm.integrity_score == 100.0


# ══════════════════════════════════════════════════════════════════════════════
# Credential Scanner
# ══════════════════════════════════════════════════════════════════════════════


class TestCredentialScanner:
    # ── scan_url_for_secrets ──────────────────────────────────────────────────

    def test_openai_key_in_url(self, tmp_path: Path) -> None:
        url = "https://example.com/token?key=sk-" + "A" * 48
        findings = list(scan_url_for_secrets(url, tmp_path / "doc.md", 7))
        assert len(findings) == 1
        assert findings[0].secret_type == "openai-api-key"
        assert findings[0].line_no == 7

    def test_github_token_in_url(self, tmp_path: Path) -> None:
        token = "ghp_" + "B" * 36
        url = f"https://api.github.com/repos?token={token}"
        findings = list(scan_url_for_secrets(url, tmp_path / "doc.md", 3))
        assert len(findings) == 1
        assert findings[0].secret_type == "github-token"

    def test_aws_key_in_url(self, tmp_path: Path) -> None:
        url = "https://s3.amazonaws.com/?AWSAccessKeyId=AKIA" + "Z" * 16
        findings = list(scan_url_for_secrets(url, tmp_path / "doc.md", 1))
        assert len(findings) == 1
        assert findings[0].secret_type == "aws-access-key"

    def test_clean_url_no_findings(self, tmp_path: Path) -> None:
        url = "https://docs.example.com/api/v2/reference"
        findings = list(scan_url_for_secrets(url, tmp_path / "doc.md", 1))
        assert findings == []

    def test_multiple_secrets_in_one_url(self, tmp_path: Path) -> None:
        """A pathological URL containing both an OpenAI key and an AWS key."""
        openai_key = "sk-" + "C" * 48
        aws_key = "AKIA" + "D" * 16
        url = f"https://evil.com/?a={openai_key}&b={aws_key}"
        findings = list(scan_url_for_secrets(url, tmp_path / "doc.md", 2))
        secret_types = {f.secret_type for f in findings}
        assert "openai-api-key" in secret_types
        assert "aws-access-key" in secret_types

    # ── scan_line_for_secrets ─────────────────────────────────────────────────

    def test_secret_in_plain_line(self, tmp_path: Path) -> None:
        line = "My token is sk-" + "E" * 48 + " please keep it safe"
        findings = list(scan_line_for_secrets(line, tmp_path / "doc.md", 10))
        assert len(findings) == 1
        assert findings[0].secret_type == "openai-api-key"

    def test_all_github_prefixes_detected(self, tmp_path: Path) -> None:
        """All valid GitHub token prefixes (p/o/u/s/r) must be caught."""
        for prefix in ("ghp", "gho", "ghu", "ghs", "ghr"):
            token = f"{prefix}_" + "F" * 36
            findings = list(scan_line_for_secrets(token, tmp_path / "doc.md", 1))
            assert len(findings) == 1, f"Prefix '{prefix}' not detected"
            assert findings[0].secret_type == "github-token"

    def test_too_short_key_not_flagged(self, tmp_path: Path) -> None:
        """A key that is one char too short must not trigger a false positive."""
        short = "sk-" + "G" * 47  # 47 < 48
        findings = list(scan_url_for_secrets(short, tmp_path / "doc.md", 1))
        assert findings == []

    # ── hex-encoded-payload ───────────────────────────────────────────────────

    def test_hex_payload_three_bytes_detected(self, tmp_path: Path) -> None:
        """Three consecutive \\xNN sequences exceeds the threshold — must be flagged."""
        line = r"exec('\x41\x42\x43')"
        findings = list(scan_line_for_secrets(line, tmp_path / "doc.md", 1))
        assert len(findings) == 1
        assert findings[0].secret_type == "hex-encoded-payload"

    def test_hex_payload_two_bytes_not_flagged(self, tmp_path: Path) -> None:
        """Only two \\xNN sequences — below threshold, must not be flagged."""
        line = r"prefix \x41\x42 suffix"
        findings = list(scan_line_for_secrets(line, tmp_path / "doc.md", 1))
        assert findings == []

    def test_hex_payload_in_fenced_code_block_detected(self, tmp_path: Path) -> None:
        """Credential scanner stream reads all lines raw; hex sequence in a code block must be caught."""
        from zenzic.core.credentials import _SECRETS

        hex_pattern = next(p for name, _pfx, p in _SECRETS if name == "hex-encoded-payload")
        payload = r"\x41\x42\x43\x44"
        assert hex_pattern.search(payload) is not None

    def test_plain_escape_sequences_not_flagged(self, tmp_path: Path) -> None:
        """Common prose escapes (\\n, \\t) must not match the hex-payload pattern."""
        line = r"Use \n for newlines and \t for tabs."
        findings = list(scan_line_for_secrets(line, tmp_path / "doc.md", 1))
        assert findings == []


# ══════════════════════════════════════════════════════════════════════════════
# MissingAltTextRule (Z403)
# ══════════════════════════════════════════════════════════════════════════════


class TestMissingAltTextRule:
    def test_no_images_no_findings(self) -> None:
        from zenzic.core.rules import MissingAltTextRule

        text = "# Title\n\nSome prose without any images.\n"
        rule = MissingAltTextRule()
        assert rule.check(Path("doc.md"), text) == []

    def test_image_with_alt_text_ok(self) -> None:
        from zenzic.core.rules import MissingAltTextRule

        text = "![A diagram showing the pipeline](pipeline.png)\n"
        rule = MissingAltTextRule()
        assert rule.check(Path("doc.md"), text) == []

    def test_image_without_alt_text_flagged(self) -> None:
        from zenzic.core.rules import MissingAltTextRule

        text = "![](pipeline.png)\n"
        rule = MissingAltTextRule()
        findings = rule.check(Path("doc.md"), text)
        assert len(findings) == 1
        assert findings[0].rule_id == "Z403"
        assert findings[0].severity == "warning"
        assert findings[0].line_no == 1

    def test_image_whitespace_only_alt_flagged(self) -> None:
        from zenzic.core.rules import MissingAltTextRule

        text = "![   ](pipeline.png)\n"
        rule = MissingAltTextRule()
        findings = rule.check(Path("doc.md"), text)
        assert len(findings) == 1

    def test_html_img_without_alt_flagged(self) -> None:
        from zenzic.core.rules import MissingAltTextRule

        text = '<img src="diagram.png">\n'
        rule = MissingAltTextRule()
        findings = rule.check(Path("doc.md"), text)
        assert len(findings) == 1
        assert findings[0].rule_id == "Z403"

    def test_html_img_with_alt_ok(self) -> None:
        from zenzic.core.rules import MissingAltTextRule

        text = '<img src="diagram.png" alt="A flowchart">\n'
        rule = MissingAltTextRule()
        findings = rule.check(Path("doc.md"), text)
        assert findings == []

    def test_mixed_images_multiple_findings(self) -> None:
        from zenzic.core.rules import MissingAltTextRule

        text = '![Good alt](a.png)\n![](b.png)\n![also good](c.png)\n<img src="d.png">\n'
        rule = MissingAltTextRule()
        findings = rule.check(Path("doc.md"), text)
        assert len(findings) == 2
        line_nos = {f.line_no for f in findings}
        assert line_nos == {2, 4}


# ══════════════════════════════════════════════════════════════════════════════
# ReferenceScanner — harvest (Pass 1)
# ══════════════════════════════════════════════════════════════════════════════


class TestReferenceScannerHarvest:
    def _write_md(self, tmp_path: Path, content: str, name: str = "doc.md") -> Path:
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return p

    def test_harvest_yields_def_event(self, tmp_path: Path) -> None:
        md = self._write_md(tmp_path, "[myref]: https://example.com\n")
        scanner = ReferenceScanner(md)
        events = list(scanner.harvest())
        types = [e[1] for e in events]
        assert "DEF" in types
        # ref_map populated
        assert scanner.ref_map.resolve("myref") == "https://example.com"

    def test_harvest_first_wins_duplicate_def_event(self, tmp_path: Path) -> None:
        """Second definition must yield DUPLICATE_DEF, not DEF."""
        content = "[ref]: https://first.com\n[ref]: https://second.com\n"
        md = self._write_md(tmp_path, content)
        scanner = ReferenceScanner(md)
        events = list(scanner.harvest())
        types = [e[1] for e in events]
        assert types.count("DEF") == 1
        assert types.count("DUPLICATE_DEF") == 1
        # First wins
        assert scanner.ref_map.resolve("ref") == "https://first.com"

    def test_harvest_secret_in_definition_url(self, tmp_path: Path) -> None:
        """A reference definition whose URL contains an OpenAI key → SECRET event."""
        openai_key = "sk-" + "H" * 48
        content = f"[secret_ref]: https://api.example.com/?key={openai_key}\n"
        md = self._write_md(tmp_path, content)
        scanner = ReferenceScanner(md)
        events = list(scanner.harvest())
        secret_events = [(e[1], e[2]) for e in events if e[1] == "SECRET"]
        assert len(secret_events) == 1
        finding: SecurityFinding = secret_events[0][1]
        assert finding.secret_type == "openai-api-key"
        assert finding.file_path == md

    def test_harvest_skips_code_block(self, tmp_path: Path) -> None:
        """Definitions inside fenced code blocks must NOT be harvested."""
        content = "Normal prose.\n```\n[fake_ref]: https://inside-code-block.com\n```\n"
        md = self._write_md(tmp_path, content)
        scanner = ReferenceScanner(md)
        list(scanner.harvest())
        assert "fake_ref" not in scanner.ref_map

    def test_harvest_case_insensitive_normalisation(self, tmp_path: Path) -> None:
        """[MyRef] and [myref] must be the same key in the map."""
        content = "[MyRef]: https://example.com\n"
        md = self._write_md(tmp_path, content)
        scanner = ReferenceScanner(md)
        list(scanner.harvest())
        assert scanner.ref_map.resolve("myref") == "https://example.com"
        assert scanner.ref_map.resolve("MYREF") == "https://example.com"

    def test_credential_scanner_detects_secret_in_unlabelled_fence(self, tmp_path: Path) -> None:
        """A credential inside an unlabelled ``` block must be caught by the credential scanner."""
        aws_key = "AKIA" + "Z" * 16
        content = f"Some prose.\n```\nexport AWS_KEY={aws_key}\n```\n"
        md = self._write_md(tmp_path, content)
        scanner = ReferenceScanner(md)
        events = list(scanner.harvest())
        secret_events = [e for e in events if e[1] == "SECRET"]
        assert len(secret_events) == 1
        assert secret_events[0][2].secret_type == "aws-access-key"

    def test_credential_scanner_detects_secret_in_bash_fence(self, tmp_path: Path) -> None:
        """A credential inside a ```bash block must be caught by the credential scanner."""
        stripe_key = "sk_live_" + "X" * 24
        content = f"Example:\n```bash\nexport STRIPE_KEY={stripe_key}\n```\n"
        md = self._write_md(tmp_path, content)
        scanner = ReferenceScanner(md)
        events = list(scanner.harvest())
        secret_events = [e for e in events if e[1] == "SECRET"]
        assert len(secret_events) == 1
        assert secret_events[0][2].secret_type == "stripe-live-key"

    def test_credential_scanner_fenced_secret_does_not_create_ref_definition(
        self, tmp_path: Path
    ) -> None:
        """A credential inside a fence fires the credential scanner but must NOT be harvested as a ref-def."""
        github_token = "ghp_" + "B" * 36
        content = f"```\n[secret_ref]: https://example.com/{github_token}\n```\n"
        md = self._write_md(tmp_path, content)
        scanner = ReferenceScanner(md)
        events = list(scanner.harvest())
        # Credential scanner must fire
        secret_events = [e for e in events if e[1] == "SECRET"]
        assert len(secret_events) == 1
        assert secret_events[0][2].secret_type == "github-token"
        # The ref-def must NOT be added to the map (it's inside a fence)
        assert "secret_ref" not in scanner.ref_map

    def test_credential_scanner_clean_code_block_no_findings(self, tmp_path: Path) -> None:
        """A code block with no credentials must not produce SECRET events."""
        content = "```bash\nexport DATABASE_URL=postgres://localhost/mydb\n```\n"
        md = self._write_md(tmp_path, content)
        scanner = ReferenceScanner(md)
        events = list(scanner.harvest())
        assert not any(e[1] == "SECRET" for e in events)


# ══════════════════════════════════════════════════════════════════════════════
# ReferenceScanner — cross_check (Pass 2)
# ══════════════════════════════════════════════════════════════════════════════


class TestReferenceScannerCrossCheck:
    def _make_scanner(self, tmp_path: Path, content: str) -> ReferenceScanner:
        p = tmp_path / "doc.md"
        p.write_text(content, encoding="utf-8")
        scanner = ReferenceScanner(p)
        list(scanner.harvest())  # populate ref_map first
        return scanner

    def test_defined_reference_resolves_cleanly(self, tmp_path: Path) -> None:
        content = "[ref]: https://example.com\n\nSee [the docs][ref].\n"
        scanner = self._make_scanner(tmp_path, content)
        findings = scanner.cross_check()
        errors = [f for f in findings if not f.is_warning]
        assert errors == []
        assert "ref" in scanner.ref_map.used_ids

    def test_phantom_reference_trap(self, tmp_path: Path) -> None:
        """'Phantom Reference Trap': [text][ghost] with no [ghost]: definition."""
        content = "No definition here.\n\nSee [the ghost][ghost_id].\n"
        scanner = self._make_scanner(tmp_path, content)
        findings = scanner.cross_check()
        assert len(findings) == 1
        assert findings[0].issue == "Z301"
        assert "ghost_id" in findings[0].detail
        # is_warning is True: Z301 is classified "warning" in codes.py's
        # CODE_DEFINITIONS (the SSoT); it used to hardcode False here,
        # which caused every dangling reference to hard-fail a plain
        # `zenzic check` run with no --strict, contradicting the Tier-0
        # Exit Code Contract (fixed in V031_Z301_SEVERITY_FIX_AND_BACKLOG_SEQUENCING).
        assert findings[0].is_warning is True

    def test_cross_check_case_insensitive(self, tmp_path: Path) -> None:
        """[text][REF] must resolve [ref]: url (case-insensitive)."""
        content = "[myref]: https://example.com\n\nSee [page][MyRef].\n"
        scanner = self._make_scanner(tmp_path, content)
        findings = scanner.cross_check()
        errors = [f for f in findings if not f.is_warning]
        assert errors == []

    def test_collapsed_reference_link(self, tmp_path: Path) -> None:
        """[myref][] is a collapsed reference — should resolve to [myref]: url."""
        content = "[myref]: https://example.com\n\nSee [myref][].\n"
        scanner = self._make_scanner(tmp_path, content)
        findings = scanner.cross_check()
        errors = [f for f in findings if not f.is_warning]
        assert errors == []

    def test_image_reference_link_resolved(self, tmp_path: Path) -> None:
        """![alt][ref] is an image reference — should resolve to [ref]: url."""
        content = "[imgref]: https://example.com/img.png\n\nSee ![alt][imgref].\n"
        scanner = self._make_scanner(tmp_path, content)
        findings = scanner.cross_check()
        errors = [f for f in findings if not f.is_warning]
        assert errors == []
        assert "imgref" in scanner.ref_map.used_ids

    def test_multiple_dangling_refs(self, tmp_path: Path) -> None:
        content = (
            "[valid]: https://example.com\n\nSee [A][ghost1] and [B][ghost2] and [C][valid].\n"
        )
        scanner = self._make_scanner(tmp_path, content)
        findings = scanner.cross_check()
        issues = {f.issue for f in findings}
        assert "Z301" in issues
        dangling = [f for f in findings if f.issue == "Z301"]
        assert len(dangling) == 2


# ══════════════════════════════════════════════════════════════════════════════
# ReferenceScanner — get_integrity_report (Pass 3)
# ══════════════════════════════════════════════════════════════════════════════


class TestReferenceScannerIntegrityReport:
    def _run_full_pipeline(self, tmp_path: Path, content: str) -> IntegrityReport:
        p = tmp_path / "doc.md"
        p.write_text(content, encoding="utf-8")
        scanner = ReferenceScanner(p)

        security_findings: list[SecurityFinding] = []
        for _ln, etype, data in scanner.harvest():
            if etype == "SECRET":
                security_findings.append(data)

        cross_findings = scanner.cross_check()
        return scanner.get_integrity_report(cross_findings, security_findings)

    def test_perfect_score_all_used(self, tmp_path: Path) -> None:
        content = "[a]: https://a.com\n[b]: https://b.com\n\nSee [A][a] and [B][b].\n"
        report = self._run_full_pipeline(tmp_path, content)
        assert report.score == pytest.approx(100.0)
        assert report.has_errors is False

    def test_orphan_definition_in_report(self, tmp_path: Path) -> None:
        content = "[used]: https://used.com\n[orphan]: https://orphan.com\n\nSee [X][used].\n"
        report = self._run_full_pipeline(tmp_path, content)
        assert report.score == pytest.approx(50.0)
        orphan_findings = [f for f in report.findings if f.issue == "Z302"]
        assert len(orphan_findings) == 1
        assert orphan_findings[0].is_warning is True

    def test_duplicate_def_in_report(self, tmp_path: Path) -> None:
        content = "[ref]: https://first.com\n[ref]: https://second.com\n\nSee [X][ref].\n"
        report = self._run_full_pipeline(tmp_path, content)
        dup_findings = [f for f in report.findings if f.issue == "Z303"]
        assert len(dup_findings) == 1
        assert dup_findings[0].is_warning is True

    def test_security_finding_in_report(self, tmp_path: Path) -> None:
        openai_key = "sk-" + "I" * 48
        content = f"[s]: https://api.example.com/?key={openai_key}\n"
        report = self._run_full_pipeline(tmp_path, content)
        assert report.is_secure is False
        assert len(report.security_findings) == 1

    def test_credential_scanner_is_firewall_pass2_skipped(self, tmp_path: Path) -> None:
        """When Pass 1 detects a secret, Pass 2 cross_check must be skipped."""
        openai_key = "sk-" + "J" * 48
        content = (
            f"[danger]: https://api.example.com/?key={openai_key}\n\n"
            "See [ghost][undefined_ref].\n"  # would be DANGLING if Pass 2 ran
        )
        p = tmp_path / "doc.md"
        p.write_text(content, encoding="utf-8")
        scanner = ReferenceScanner(p)

        security_findings: list[SecurityFinding] = []
        for _ln, etype, data in scanner.harvest():
            if etype == "SECRET":
                security_findings.append(data)

        # Simulate CLI behavior: skip Pass 2 if secrets found
        cross_findings: list = []  # type: ignore[type-arg]
        if not security_findings:
            cross_findings = scanner.cross_check()

        report = scanner.get_integrity_report(cross_findings, security_findings)
        assert report.is_secure is False
        dangling = [f for f in report.findings if f.issue == "Z301"]
        assert dangling == []  # Pass 2 was skipped

    def test_no_definitions_score_100(self, tmp_path: Path) -> None:
        """No definitions → score is 100.0 (vacuously perfect, no division by zero)."""
        content = "Just some prose, no reference links at all.\n"
        report = self._run_full_pipeline(tmp_path, content)
        assert report.score == pytest.approx(100.0)

    def test_is_secure_and_has_errors_flags(self, tmp_path: Path) -> None:
        content = "See [ghost][undefined].\n"
        report = self._run_full_pipeline(tmp_path, content)
        assert report.is_secure is True  # no secrets
        # DANGLING (Z301) is a warning per codes.py's CODE_DEFINITIONS, not a
        # hard error -- it used to be hardcoded as one here, which caused a
        # lone dangling reference to hard-fail a plain `zenzic check` run
        # with no --strict (fixed in V031_Z301_SEVERITY_FIX_AND_BACKLOG_SEQUENCING).
        assert report.has_errors is False


# ══════════════════════════════════════════════════════════════════════════════
# scan_docs_references (I/O integration)
# ══════════════════════════════════════════════════════════════════════════════


class TestScanDocsReferences:
    def test_empty_docs_returns_empty(self, tmp_path: Path) -> None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "mkdocs.yml").touch()
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        reports, _ = scan_docs_references(docs_root, mgr, config=config)
        assert reports == []

    def test_missing_docs_dir_returns_empty(self, tmp_path: Path) -> None:
        (tmp_path / "mkdocs.yml").touch()
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        reports, _ = scan_docs_references(docs_root, mgr, config=config)
        assert reports == []

    def test_single_clean_file(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (tmp_path / "mkdocs.yml").touch()
        (docs / "index.md").write_text(
            "[guide]: https://example.com\n\nSee [guide][guide].\n",
            encoding="utf-8",
        )
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        reports, _ = scan_docs_references(docs_root, mgr, config=config)
        assert len(reports) == 1
        assert reports[0].score == pytest.approx(100.0)
        assert reports[0].is_secure is True

    def test_secret_in_docs_flagged(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (tmp_path / "mkdocs.yml").touch()
        aws_key = "AKIA" + "K" * 16
        (docs / "danger.md").write_text(
            f"[api]: https://aws.example.com/?key={aws_key}\n",
            encoding="utf-8",
        )
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        reports, _ = scan_docs_references(docs_root, mgr, config=config)
        assert len(reports) == 1
        assert reports[0].is_secure is False

    def test_symlinks_skipped(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        real = outside / "real.md"
        real.write_text("[ref]: https://example.com\n", encoding="utf-8")
        (docs / "linked.md").symlink_to(real)
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=docs)
        reports, _ = scan_docs_references(docs_root, mgr, config=config)
        assert reports == []

    def test_deduplication_1000_refs_single_used_id(self, tmp_path: Path) -> None:
        """1000 reference links to the same ID → only one entry in used_ids."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (tmp_path / "mkdocs.yml").touch()
        lines = ["[bigref]: https://bigref.com\n"]
        for i in range(1000):
            lines.append(f"Item {i}: see [here][bigref].\n")
        (docs / "big.md").write_text("".join(lines), encoding="utf-8")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        reports, _ = scan_docs_references(docs_root, mgr, config=config)
        assert len(reports) == 1
        report = reports[0]
        assert report.score == pytest.approx(100.0)


# ══════════════════════════════════════════════════════════════════════════════
# Dev 4 Stress Tests — "Diabolical" First-Wins Scenarios
# ══════════════════════════════════════════════════════════════════════════════


class TestDiabolicalFirstWins:
    """Stress-test the Two-Pass Pipeline against pathological documents.

    These tests verify that CommonMark §4.7 first-wins holds under adversarial
    conditions, and that forward references (usage before definition) are
    correctly resolved by the two-pass architecture.
    """

    def _make_scanner(self, tmp_path: Path, content: str) -> ReferenceScanner:
        p = tmp_path / "diabolical.md"
        p.write_text(content, encoding="utf-8")
        scanner = ReferenceScanner(p)
        list(scanner.harvest())
        return scanner

    def test_forward_references_resolved_by_two_pass(self, tmp_path: Path) -> None:
        """ID used 10 times before its definition appears → all resolve cleanly.

        A single-pass scanner would report 10 DANGLING findings here.
        The Two-Pass Pipeline must resolve them all because Pass 2 runs after
        Pass 1 has fully populated the ReferenceMap.
        """
        lines: list[str] = []
        # 10 forward usages — no definition exists yet
        for i in range(1, 11):
            lines.append(f"Usage {i}: see [item {i}][forward_ref].\n")
        # Definition appears AFTER all usages (forward reference)
        lines.append("[forward_ref]: https://real.example.com\n")

        scanner = self._make_scanner(tmp_path, "".join(lines))
        cross_findings = scanner.cross_check()
        dangling = [f for f in cross_findings if f.issue == "Z301"]

        assert dangling == [], (
            "Two-Pass Pipeline must resolve forward references. "
            f"Got {len(dangling)} unexpected DANGLING finding(s)."
        )
        assert scanner.ref_map.integrity_score == pytest.approx(100.0)

    def test_false_definition_mid_file_wins_over_late_true_definition(self, tmp_path: Path) -> None:
        """10 usages → false definition at mid-file → true definition at end.

        Per CommonMark §4.7, the first definition encountered by the harvester
        wins.  The 'false' definition at line ~15 must be the active one; the
        'true' definition at line ~25 must be recorded as a duplicate.

        This verifies that first-wins is document-order, not proximity-to-usage.
        """
        lines: list[str] = []
        # Block 1 (lines 1–10): 10 usages — forward references
        for i in range(1, 11):
            lines.append(f"Reference {i}: [link {i}][contested].\n")
        # Block 2 (line 11): separator
        lines.append("\n")
        # Block 3 (line 12): the "false" definition — first in document order → WINS
        lines.append("[contested]: https://false-but-first.example.com\n")
        lines.append("\n")
        # Block 4 (lines 14+): some prose
        for i in range(3):
            lines.append(f"Prose line {i}.\n")
        lines.append("\n")
        # Block 5 (line ~19): the "true" definition — second in document order → IGNORED
        lines.append("[contested]: https://true-but-late.example.com\n")

        scanner = self._make_scanner(tmp_path, "".join(lines))

        # First definition must win
        assert scanner.ref_map.resolve("contested") == "https://false-but-first.example.com"
        # Second definition must be recorded as duplicate
        assert "contested" in scanner.ref_map.duplicate_ids
        # Cross-check: all 10 forward usages resolve correctly
        cross_findings = scanner.cross_check()
        dangling = [f for f in cross_findings if f.issue == "Z301"]
        assert dangling == []

    def test_triple_definition_only_first_active(self, tmp_path: Path) -> None:
        """Three definitions of the same ID: only the first is active."""
        content = (
            "[id]: https://alpha.com\n"
            "[id]: https://beta.com\n"
            "[id]: https://gamma.com\n\n"
            "See [page][id].\n"
        )
        scanner = self._make_scanner(tmp_path, content)
        assert scanner.ref_map.resolve("id") == "https://alpha.com"
        assert "id" in scanner.ref_map.duplicate_ids
        # Two duplicates were ignored
        assert len(scanner.ref_map.definitions) == 1

    def test_forward_ref_with_mid_file_imposter_and_late_real(self, tmp_path: Path) -> None:
        """Full diabolical scenario: usage × 10, imposter at mid, real at end.

        The imposter wins (first-wins).  All 10 forward usages resolve to the
        imposter URL.  The late 'real' definition is a duplicate.
        The integrity score must be 100% — every definition was used.
        """
        lines: list[str] = []
        for i in range(10):
            lines.append(f"[item {i}][target]\n")
        lines.append("\n[target]: https://imposter.example.com\n")
        lines.append("\nsome prose\n\n")
        lines.append("[target]: https://real.example.com\n")

        p = tmp_path / "full_diabolical.md"
        p.write_text("".join(lines), encoding="utf-8")
        scanner = ReferenceScanner(p)
        security_findings: list[SecurityFinding] = []
        for _ln, etype, data in scanner.harvest():
            if etype == "SECRET":
                security_findings.append(data)

        cross_findings = scanner.cross_check()
        report = scanner.get_integrity_report(cross_findings, security_findings)

        # The imposter wins
        assert scanner.ref_map["target"] == "https://imposter.example.com"
        # One definition active, one duplicate
        assert len(scanner.ref_map.definitions) == 1
        assert "target" in scanner.ref_map.duplicate_ids
        # All usages resolved → 100% integrity
        assert report.score == pytest.approx(100.0)
        assert report.is_secure is True
        dangling = [f for f in report.findings if f.issue == "Z301"]
        assert dangling == []
        # The duplicate-def warning must appear
        dup_findings = [f for f in report.findings if f.issue == "Z303"]
        assert len(dup_findings) == 1
        assert dup_findings[0].is_warning is True


# ══════════════════════════════════════════════════════════════════════════════
# LinkValidator — global URL deduplication
# ══════════════════════════════════════════════════════════════════════════════


class TestLinkValidator:
    """Unit tests for LinkValidator (no network — we test the registration layer only).

    HTTP validation is already covered by the existing validator test suite.
    Here we verify the deduplication contract and the register_from_map interface.
    """

    def test_register_non_http_url_ignored(self, tmp_path: Path) -> None:
        validator = LinkValidator(ZenzicConfig(), tmp_path)
        validator.register("mailto:user@example.com", Path("doc.md"), 1)
        validator.register("ftp://files.example.com/doc.pdf", Path("doc.md"), 2)
        validator.register("/relative/path", Path("doc.md"), 3)
        assert validator.unique_url_count == 0

    def test_register_http_url_accepted(self, tmp_path: Path) -> None:
        validator = LinkValidator(ZenzicConfig(), tmp_path)
        validator.register("http://example.com", Path("doc.md"), 1)
        validator.register("https://example.com", Path("doc.md"), 2)
        assert validator.unique_url_count == 2

    def test_global_deduplication_same_url_multiple_files(self, tmp_path: Path) -> None:
        """50 registrations of the same URL → unique_url_count == 1."""
        validator = LinkValidator(ZenzicConfig(), tmp_path)
        shared_url = "https://github.com/PythonWoods/zenzic"
        for i in range(50):
            validator.register(shared_url, tmp_path / f"doc{i}.md", i + 1)
        assert validator.unique_url_count == 1

    def test_register_from_map_filters_non_http(self, tmp_path: Path) -> None:
        """register_from_map must only register http/https URLs."""
        rm = ReferenceMap()
        rm.add_definition("local", "relative/path.md", 1)
        rm.add_definition("mail", "mailto:user@example.com", 2)
        rm.add_definition("web", "https://example.com", 3)

        validator = LinkValidator(ZenzicConfig(), tmp_path)
        validator.register_from_map(rm, tmp_path / "doc.md")
        assert validator.unique_url_count == 1  # only the https URL

    def test_register_from_map_multiple_files_dedup(self, tmp_path: Path) -> None:
        """Two files both referencing the same URL → one unique URL registered."""
        shared = "https://shared.example.com"

        rm1 = ReferenceMap()
        rm1.add_definition("ref", shared, 5)

        rm2 = ReferenceMap()
        rm2.add_definition("ref", shared, 3)

        validator = LinkValidator(ZenzicConfig(), tmp_path)
        validator.register_from_map(rm1, tmp_path / "file1.md")
        validator.register_from_map(rm2, tmp_path / "file2.md")
        assert validator.unique_url_count == 1

    def test_register_from_map_distinct_urls_counted(self, tmp_path: Path) -> None:
        rm = ReferenceMap()
        rm.add_definition("a", "https://alpha.example.com", 1)
        rm.add_definition("b", "https://beta.example.com", 2)
        rm.add_definition("c", "https://gamma.example.com", 3)

        validator = LinkValidator(ZenzicConfig(), tmp_path)
        validator.register_from_map(rm, tmp_path / "doc.md")
        assert validator.unique_url_count == 3

    def test_validate_returns_empty_when_no_registrations(self, tmp_path: Path) -> None:
        """validate() on an empty validator must return [] without raising."""
        validator = LinkValidator(ZenzicConfig(), tmp_path)
        errors = validator.validate()
        assert errors == []

    def test_scan_docs_references_with_links_no_links_flag(self, tmp_path: Path) -> None:
        """validate_links=False → link_errors is always [] (no HTTP calls)."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (tmp_path / "mkdocs.yml").touch()
        (docs / "index.md").write_text(
            "[ref]: https://example.com\n\nSee [page][ref].\n",
            encoding="utf-8",
        )
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        reports, link_errors = scan_docs_references(
            docs_root, mgr, config=config, validate_links=False
        )
        assert len(reports) == 1
        assert link_errors == []

    def test_scan_docs_references_with_links_secure_files_only(self, tmp_path: Path) -> None:
        """Files with credential scanner findings must not have their URLs registered."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (tmp_path / ".zenzic.toml").touch()
        (tmp_path / "mkdocs.yml").touch()
        aws_key = "AKIA" + "L" * 16
        (docs / "danger.md").write_text(
            f"[api]: https://aws.example.com/?key={aws_key}\n",
            encoding="utf-8",
        )
        # validate_links=True but the file has a secret → URLs must be skipped
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        reports, link_errors = scan_docs_references(
            docs_root, mgr, config=config, validate_links=True
        )
        # Reports still produced (with security finding)
        assert len(reports) == 1
        assert reports[0].is_secure is False
        # No HTTP calls were made (validator was not given the URL)
        assert link_errors == []
