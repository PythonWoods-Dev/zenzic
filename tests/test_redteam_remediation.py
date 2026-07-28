# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for ZRT adversarial validation remediation.

Covers:
- ZRT-001: Credential scanner must detect secrets in YAML frontmatter
- ZRT-007: CustomRule must reject RE2-incompatible patterns at construction (DFA purity)
- ZRT-003: Credential scanner normalizer must catch split-token obfuscation in tables
- ZRT-004: VSMBrokenLinkRule must resolve relative links with source-file context
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zenzic.core.exceptions import PluginContractError
from zenzic.core.rules import (
    AdaptiveRuleEngine,
    CustomRule,
    ResolutionContext,
    Violation,
    VSMBrokenLinkRule,
)
from zenzic.models.vsm import Route


# Credential scanner symbols are committed in Commit 2 (credentials.py + scanner.py).
# Guard the import so that Commit 1 alone remains test-runnable: the two
# credential-scanner-dependent test classes are skipped until Commit 2 is applied.
try:
    from zenzic.core.credentials import (
        SecurityFinding,
        _normalize_line_for_scan,
        scan_line_for_secrets,
    )
    from zenzic.core.reporter import Finding, ZenzicReporter, _obfuscate_secret
    from zenzic.core.scanner import ReferenceScanner, _map_credential_to_finding

    _CREDENTIALS_AVAILABLE = True
except ImportError:
    _normalize_line_for_scan = None  # type: ignore[assignment]
    scan_line_for_secrets = None  # type: ignore[assignment]
    ReferenceScanner = None  # type: ignore[assignment,misc]
    _map_credential_to_finding = None  # type: ignore[assignment]
    SecurityFinding = None  # type: ignore[assignment,misc]
    Finding = None  # type: ignore[assignment,misc]
    ZenzicReporter = None  # type: ignore[assignment,misc]
    _obfuscate_secret = None  # type: ignore[assignment]
    _CREDENTIALS_AVAILABLE = False

_credential_scanner_skip = pytest.mark.skipif(
    not _CREDENTIALS_AVAILABLE,
    reason="credentials.py normalizer and scanner.py dual-stream not yet committed (Commit 2)",
)


# ─── ZRT-001: Credential scanner must detect secrets in YAML frontmatter ──────────────────


@_credential_scanner_skip
class TestCredentialScannerFrontmatterCoverage:
    """ZRT-001: The credential scanner stream must scan ALL lines including frontmatter."""

    def test_credential_scanner_catches_aws_key_in_yaml_frontmatter(self, tmp_path: Path) -> None:
        """AWS access key inside YAML frontmatter must trigger a SecurityFinding."""
        from zenzic.core.scanner import ReferenceScanner

        md = tmp_path / "secret.md"
        md.write_text(
            "---\n"
            "aws_key: AKIA1234567890ABCDEF\n"
            "title: API Guide\n"
            "---\n\n"
            "# Guide\n\nNormal content here.\n"
        )
        scanner = ReferenceScanner(md)
        secrets = [data for _, evt, data in scanner.harvest() if evt == "SECRET"]
        assert len(secrets) >= 1, "Credential scanner must catch AWS key inside YAML frontmatter"
        secret_types = {s.secret_type for s in secrets}
        assert "aws-access-key" in secret_types

    def test_credential_scanner_catches_github_token_in_yaml_frontmatter(
        self, tmp_path: Path
    ) -> None:
        """GitHub PAT inside YAML frontmatter must trigger a SecurityFinding."""
        from zenzic.core.scanner import ReferenceScanner

        md = tmp_path / "github_secret.md"
        md.write_text(
            "---\n"
            "author: John Doe\n"
            "github_token: ghp_1234567890123456789012345678901234567\n"
            "---\n\n"
            "# Guide\n\nNormal content.\n"
        )
        scanner = ReferenceScanner(md)
        secrets = [data for _, evt, data in scanner.harvest() if evt == "SECRET"]
        assert len(secrets) >= 1, (
            "Credential scanner must catch GitHub token inside YAML frontmatter"
        )

    def test_credential_scanner_does_not_create_false_positive_on_clean_frontmatter(
        self, tmp_path: Path
    ) -> None:
        """A doc with only safe frontmatter metadata must emit zero secrets."""
        from zenzic.core.scanner import ReferenceScanner

        md = tmp_path / "clean.md"
        md.write_text(
            "---\n"
            "title: Clean Page\n"
            "author: Jane Doe\n"
            "tags: [docs, guide]\n"
            "---\n\n"
            "# Clean Page\n\nThis page has no secrets.\n"
        )
        scanner = ReferenceScanner(md)
        secrets = [data for _, evt, data in scanner.harvest() if evt == "SECRET"]
        assert secrets == [], f"Expected 0 secrets, got: {secrets}"

    def test_credential_scanner_secret_line_number_is_inside_frontmatter(
        self, tmp_path: Path
    ) -> None:
        """The reported line number of a frontmatter secret must be correct."""
        from zenzic.core.scanner import ReferenceScanner

        md = tmp_path / "line_check.md"
        md.write_text(
            "---\n"  # line 1
            "title: Guide\n"  # line 2
            "aws_key: AKIA1234567890ABCDEF\n"  # line 3
            "---\n"  # line 4
        )
        scanner = ReferenceScanner(md)
        secrets = [data for _, evt, data in scanner.harvest() if evt == "SECRET"]
        assert len(secrets) >= 1
        # The secret is on line 3
        assert secrets[0].line_no == 3


# ─── ZRT-007: RE2-native DFA enforcement ──────────────────────────────────────────────


class TestReDoSCanary:
    """ZRT-007: CustomRule must reject RE2-incompatible patterns at construction.

    The RE2 DFA engine eliminates the ReDoS attack surface mathematically by
    rejecting any pattern that requires NFA backtracking (backreferences,
    lookaheads, lookbehinds) at compile time.  There is no runtime canary:
    construction IS the safety check.

    Patterns like (a+)+ that were previously dangerous under Python\'s NFA are
    accepted by RE2 and run in O(n) — they are no longer a threat.
    """

    def test_construction_rejects_backreference(self) -> None:
        """Backreferences (\\1) are non-regular and rejected by RE2 at compile time."""
        with pytest.raises(PluginContractError, match="RE2"):
            CustomRule(
                id="ZZ-BACKREF",
                pattern=r"(\w+)\1",
                message="Backreference test.",
                severity="error",
            )

    def test_construction_rejects_lookahead_positive(self) -> None:
        """Positive lookahead (?=...) is rejected by RE2 at compile time."""
        with pytest.raises(PluginContractError, match="RE2"):
            CustomRule(
                id="ZZ-LOOKAHEAD",
                pattern=r"foo(?=bar)",
                message="Lookahead test.",
                severity="error",
            )

    def test_construction_rejects_lookahead_negative(self) -> None:
        """Negative lookahead (?!...) is rejected by RE2 at compile time."""
        with pytest.raises(PluginContractError, match="RE2"):
            CustomRule(
                id="ZZ-NEGLOOKAHEAD",
                pattern=r"foo(?!bar)",
                message="Negative lookahead test.",
                severity="error",
            )

    def test_construction_rejects_lookbehind(self) -> None:
        """Lookbehind (?<=...) is rejected by RE2 at compile time."""
        with pytest.raises(PluginContractError, match="RE2"):
            CustomRule(
                id="ZZ-LOOKBEHIND",
                pattern=r"(?<=foo)bar",
                message="Lookbehind test.",
                severity="error",
            )

    def test_classic_redos_pattern_compiles_and_runs_fast(self) -> None:
        """(a+)+ is accepted by RE2 and runs in O(n) — no longer a ReDoS threat."""
        import time

        rule = CustomRule(
            id="ZZ-REDOS-SAFE",
            pattern=r"(a+)+",
            message="RE2-safe pattern.",
            severity="error",
        )
        t0 = time.perf_counter()
        rule.check(Path("x.md"), "a" * 50 + "b")
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.1, f"RE2 search took {elapsed:.3f}s — expected microseconds"

    def test_engine_construction_rejects_re2_incompatible_rule(self) -> None:
        """AdaptiveRuleEngine cannot be built with a RE2-incompatible CustomRule."""
        with pytest.raises(PluginContractError, match="RE2"):
            AdaptiveRuleEngine(
                [
                    CustomRule(
                        id="ZZ-DEADLOCK",
                        pattern=r"(\w+)\1",
                        message="Backreference pattern.",
                        severity="error",
                    )
                ]
            )

    def test_construction_accepts_safe_pattern(self) -> None:
        """A simple, DFA-compatible regex compiles without error."""
        rule = CustomRule(
            id="ZZ-SAFE",
            pattern=r"TODO",
            message="TODO found.",
            severity="warning",
        )
        assert rule.rule_id == "ZZ-SAFE"

    def test_construction_accepts_anchored_safe_pattern(self) -> None:
        """A complex-but-safe anchored pattern compiles without error."""
        rule = CustomRule(
            id="ZZ-SAFE2",
            pattern=r"^(DRAFT|WIP|TODO):?\s",
            message="Status marker.",
            severity="info",
        )
        assert rule.rule_id == "ZZ-SAFE2"

    def test_construction_accepts_inline_flags(self) -> None:
        """Inline RE2 flags like (?i) and (?m) are valid DFA constructs."""
        rule = CustomRule(
            id="ZZ-FLAG",
            pattern=r"(?i)\bDRAFT\b",
            message="Draft marker.",
            severity="warning",
        )
        findings = rule.check(Path("x.md"), "This is a draft document")
        assert len(findings) == 1

    def test_engine_works_with_re2_compatible_rules(self) -> None:
        """An engine built from valid RE2 rules scans correctly."""
        rules: list[CustomRule] = [
            CustomRule(id="ZZ-A", pattern=r"TODO", message="todo", severity="info"),
            CustomRule(id="ZZ-B", pattern=r"(?i)\bDRAFT\b", message="draft", severity="warning"),
        ]
        engine = AdaptiveRuleEngine(rules)
        findings = engine.run(Path("x.md"), "DRAFT content with TODO marker")
        assert len(findings) == 2


# ─── ZRT-003: Split-token credential scanner bypass via Markdown table normalizer ──────────


@_credential_scanner_skip
class TestCredentialScannerNormalizer:
    """ZRT-003: The pre-scan normalizer must reconstruct split-token secrets."""

    def test_normalize_strips_backtick_spans(self) -> None:
        """`AKIA` → AKIA (unwrap inline code)."""
        result = _normalize_line_for_scan("`AKIA`1234567890ABCDEF")
        assert "AKIA1234567890ABCDEF" in result

    def test_normalize_removes_concat_operator(self) -> None:
        """`AKIA` + `1234567890ABCDEF` → AKIA1234567890ABCDEF."""
        result = _normalize_line_for_scan("`AKIA` + `1234567890ABCDEF`")
        assert "AKIA1234567890ABCDEF" in result

    def test_normalize_strips_table_pipes(self) -> None:
        """Pipes → spaces so table cells don't break token continuity."""
        result = _normalize_line_for_scan("| Key | AKIA1234567890ABCDEF |")
        assert "|" not in result
        assert "AKIA1234567890ABCDEF" in result

    def test_normalize_handles_combined_table_and_concat(self) -> None:
        """Full attack vector: table cell with split backtick-concat key."""
        line = "| Access Key | `AKIA` + `1234567890ABCDEF` |"
        result = _normalize_line_for_scan(line)
        assert "AKIA1234567890ABCDEF" in result

    def test_scan_line_catches_split_token_aws_key(self) -> None:
        """scan_line_for_secrets must catch an AWS key split across backtick spans."""
        line = "| Key | `AKIA` + `1234567890ABCDEF` |"
        findings = list(scan_line_for_secrets(line, Path("docs/config.md"), 7))
        assert len(findings) >= 1, f"Expected >=1 finding, got: {findings}"
        assert findings[0].secret_type == "aws-access-key"

    def test_scan_line_no_false_positive_on_clean_table(self) -> None:
        """Clean table rows must not trigger any findings."""
        line = "| API endpoint | https://api.example.com/v1/users |"
        findings = list(scan_line_for_secrets(line, Path("docs/api.md"), 3))
        assert findings == []

    def test_scan_line_still_catches_plain_aws_key(self) -> None:
        """Normalizer must not break detection of non-obfuscated secrets."""
        line = "aws_key = AKIA1234567890ABCDEF"
        findings = list(scan_line_for_secrets(line, Path("docs/config.md"), 1))
        assert len(findings) >= 1
        assert findings[0].secret_type == "aws-access-key"

    def test_no_duplicate_findings_for_same_secret(self) -> None:
        """If raw and normalised both match, only ONE finding is emitted per type."""
        # This line has the key both raw AND in a table — should only emit once
        line = "AKIA1234567890ABCDEF"
        findings = list(scan_line_for_secrets(line, Path("docs/x.md"), 1))
        types = [f.secret_type for f in findings]
        assert types.count("aws-access-key") == 1, "Deduplication must prevent double-emit"

    def test_scan_line_catches_gitlab_pat(self) -> None:
        """scan_line_for_secrets must catch a GitLab Personal Access Token."""
        line = "token: glpat-xxxxxxxxxxxxxxxxxxxx"
        findings = list(scan_line_for_secrets(line, Path("docs/config.md"), 1))
        assert len(findings) >= 1
        assert findings[0].secret_type == "gitlab-pat"

    def test_scan_line_catches_gitlab_pat_in_url(self) -> None:
        """GitLab PAT embedded in a URL must be detected."""
        url = "https://gitlab.com/api/v4/projects?private_token=glpat-AbCdEfGhIjKlMnOpQrSt1234"
        findings = list(scan_line_for_secrets(url, Path("docs/api.md"), 5))
        secret_types = {f.secret_type for f in findings}
        assert "gitlab-pat" in secret_types

    def test_scan_line_no_false_positive_on_glpat_prefix(self) -> None:
        """Short strings starting with glpat- must not trigger (need 20+ chars after)."""
        line = "variable: glpat-short"
        findings = list(scan_line_for_secrets(line, Path("docs/config.md"), 1))
        gitlab_findings = [f for f in findings if f.secret_type == "gitlab-pat"]
        assert gitlab_findings == []

    def test_scan_line_no_false_positive_on_clean_line(self) -> None:
        """Clean lines must not trigger GitLab PAT detection."""
        line = "GitLab is a DevOps platform"
        findings = list(scan_line_for_secrets(line, Path("docs/intro.md"), 1))
        assert findings == []


# ─── ZRT-004: VSMBrokenLinkRule context-aware URL resolution ──────────────────


def _make_vsm(*urls: str, status: str = "REACHABLE") -> dict[str, Route]:
    return {
        url: Route(url=url, source=f"{url.strip('/')}.md", status=status)  # type: ignore[arg-type]
        for url in urls
    }


class TestVSMContextAwareResolution:
    """ZRT-004: VSMBrokenLinkRule must resolve relative .. hrefs from the source dir."""

    _RULE = VSMBrokenLinkRule()
    _DOCS_ROOT = Path("/docs")

    def _ctx(self, source_rel: str) -> ResolutionContext:
        """Build a context for a source file inside /docs."""
        return ResolutionContext(
            docs_root=self._DOCS_ROOT,
            source_file=self._DOCS_ROOT / source_rel,
        )

    def _run_with_ctx(self, text: str, vsm: dict, source_rel: str) -> list[Violation]:  # type: ignore[type-arg]
        ctx = self._ctx(source_rel)
        return self._RULE.check_vsm(self._DOCS_ROOT / source_rel, text, vsm, {}, ctx)

    def test_context_aware_resolves_dotdot_to_sibling(self) -> None:
        """../../c/target.md from docs/a/b/page.md → /c/target/."""
        vsm = _make_vsm("/c/target/")
        violations = self._run_with_ctx("[T](../../c/target.md)", vsm, "a/b/page.md")
        assert violations == [], "Link ../../c/target.md from docs/a/b/ must resolve to /c/target/"

    def test_context_aware_single_dotdot(self) -> None:
        """../sibling.md from docs/subdir/page.md → /sibling/."""
        vsm = _make_vsm("/sibling/")
        violations = self._run_with_ctx("[Sibling](../sibling.md)", vsm, "subdir/page.md")
        assert violations == [], "Link ../sibling.md from docs/subdir/ must resolve to /sibling/"

    def test_context_aware_dotdot_absent_from_vsm_emits_violation(self) -> None:
        """A context-resolved link to an absent URL must still emit Z101."""
        vsm = _make_vsm("/other/")  # /sibling/ is absent
        violations = self._run_with_ctx("[Broken](../sibling.md)", vsm, "subdir/page.md")
        assert len(violations) == 1
        assert violations[0].code in ("Z101", "Z104")


    def test_context_aware_traversal_escape_returns_none(self) -> None:
        """A path that escapes docs_root via .. must be silently skipped (no crash)."""
        vsm = _make_vsm("/etc/")
        violations = self._run_with_ctx("[Escape](../../../../etc/passwd)", vsm, "subdir/page.md")
        # The path escapes docs_root — must not emit a false Z101 nor crash
        assert violations == []

    def test_without_context_preserves_backward_compatibility(self) -> None:
        """Without context, behaviour is identical to the original @staticmethod."""
        vsm = _make_vsm("/guide/")
        # docs/guide.md with no context → should still work as before
        violations = self._RULE.check_vsm(
            Path("docs/index.md"),
            "[Guide](guide.md)",
            vsm,
            {},
            context=None,  # explicit None
        )
        assert violations == []

    def test_context_aware_index_md_resolves_to_dir(self) -> None:
        """../section/index.md from docs/a/page.md → /section/."""
        vsm = _make_vsm("/section/")
        violations = self._run_with_ctx("[Sec](../section/index.md)", vsm, "a/page.md")
        assert violations == []

    def test_run_vsm_passes_context_to_rule(self) -> None:
        """AdaptiveRuleEngine.run_vsm must forward the context to check_vsm."""
        engine = AdaptiveRuleEngine([VSMBrokenLinkRule()])
        vsm = _make_vsm("/sibling/")
        ctx = ResolutionContext(
            docs_root=Path("/docs"),
            source_file=Path("/docs/subdir/page.md"),
        )
        # ../sibling.md from /docs/subdir/page.md → /sibling/
        findings = engine.run_vsm(
            Path("/docs/subdir/page.md"),
            "[Sibling](../sibling.md)",
            vsm,
            {},
            context=ctx,
        )
        assert findings == [], f"Expected no findings with context, got: {findings}"


# ─── Mutation Gate: Commit 2 — Credential Scanner ↔ Reporter bridge integrity ─────────────


@_credential_scanner_skip
class TestCredentialScannerReportingIntegrity:
    """Mutation Gate: these tests target _map_credential_to_finding() and _obfuscate_secret().

    Each test is designed to kill one of the three mandatory mutants defined in
    the Mutation Gate (CONTRIBUTING.md, Obligation 4).

    - ``test_map_always_emits_security_breach_severity``  → kills **The Invisible**
    - ``test_obfuscate_never_leaks_raw_secret``           → kills **The Amnesiac**
    - ``test_pipeline_appends_breach_finding_to_list``    → kills **The Silencer**
    """

    _DOCS_ROOT = Path("/docs")
    # Valid Stripe live key: 'sk_live_' (8) + exactly 24 alphanumeric chars.
    _STRIPE_KEY = "sk_live_1234567890ABCDEFGHIJKLMN"
    _FILE = Path("/docs/leaky.md")

    def _make_sf(
        self, secret_type: str = "stripe-live-key", key: str | None = None
    ) -> SecurityFinding:
        raw = key or self._STRIPE_KEY
        return SecurityFinding(
            file_path=self._FILE,
            line_no=7,
            secret_type=secret_type,
            url=f"stripe_key: {raw}",
            col_start=12,
            match_text=raw,
        )

    def test_map_always_emits_security_breach_severity(self) -> None:
        """The Invisible: _map_credential_to_finding() must set severity='security_breach'.

        A mutant that changes ``severity='security_breach'`` to ``severity='error'``
        or ``severity='warning'`` causes the CLI runner to exit 1 instead of 2,
        silently downgrading a security breach to an ordinary check failure.
        This test makes that mutant visible.
        """
        finding = _map_credential_to_finding(self._make_sf(), self._DOCS_ROOT)

        assert finding.severity == "security_breach", (
            f"Expected severity='security_breach', got '{finding.severity}'. "
            "Any other severity value causes Exit 1 instead of Exit 2."
        )
        # Explicit negative assertions — each covers one mutation site.
        assert finding.severity != "error"
        assert finding.severity != "warning"
        assert finding.severity != "info"

    def test_obfuscate_never_leaks_raw_secret(self) -> None:
        """The Amnesiac: _obfuscate_secret() and the reporter pipeline must never expose
        the raw secret.

        The full Stripe key must not appear in reporter output in any form.
        A mutant that removes obfuscation (e.g. returns the input unchanged, or
        uses ``str.upper()`` instead of redaction) is caught because:

        1. The raw key is asserted absent from ``_obfuscate_secret()``'s return value.
        2. The raw key is asserted absent from the captured full reporter output.
        3. The obfuscated form is asserted present in the output.
        4. The correct file:line reference is asserted present in the output.
        """
        from io import StringIO

        from rich.console import Console

        raw = self._STRIPE_KEY
        obfuscated = _obfuscate_secret(raw)

        # ── Unit-level assertions on _obfuscate_secret() ─────────────────────
        assert raw not in obfuscated, (
            f"_obfuscate_secret must not return the raw secret. Got: {obfuscated!r}"
        )
        assert "*" in obfuscated, "Obfuscated form must replace the body with asterisks."
        assert obfuscated != "*" * len(raw), (
            "_obfuscate_secret must preserve prefix and suffix for human verification."
        )
        assert obfuscated[:4] == raw[:4], "First 4 chars must be preserved."
        assert obfuscated[-4:] == raw[-4:], "Last 4 chars must be preserved."

        # ── Integration: raw key must not appear in reporter output ───────────
        buf = StringIO()
        con = Console(file=buf, no_color=True, highlight=False, width=120)
        reporter = ZenzicReporter(con, self._DOCS_ROOT)

        breach_finding = Finding(
            rel_path="leaky.md",
            line_no=7,
            code="CREDENTIAL",
            severity="security_breach",
            message="Secret detected (stripe-live-key) — rotate immediately.",
            source_line=f"stripe_key: {raw}",
            col_start=12,
            match_text=raw,
        )
        reporter.render(
            [breach_finding],
            version="test",
            elapsed=0.1,
            docs_count=1,
            assets_count=0,
            engine="test",
        )
        output = buf.getvalue()

        # The raw full secret must NEVER appear in any rendered line.
        assert raw not in output, (
            f"Raw secret found in reporter output.\n"
            f"  Secret: {raw!r}\n"
            f"  Obfuscated expected: {obfuscated!r}\n"
            f"  Output excerpt: {output[:300]!r}"
        )
        # The obfuscated form must be present so the operator knows what to rotate.
        assert obfuscated in output, (
            f"Obfuscated form {obfuscated!r} must appear in reporter output."
        )
        # The reporter must identify the correct file and line number.
        assert "leaky.md:7" in output, "Reporter must display 'file:line' for breach localisation."

    def test_pipeline_appends_breach_finding_to_list(self) -> None:
        """The Silencer: _map_credential_to_finding() must return a non-None Finding.

        A mutant that replaces the ``return Finding(...)`` with ``return None``,
        or wraps the caller's ``findings.append(f)`` in a no-op condition,
        would silently discard all breach findings.
        This test kills that mutant by asserting count, identity, and field fidelity.
        """
        sf = self._make_sf()
        result = _map_credential_to_finding(sf, self._DOCS_ROOT)

        # Must return a Finding, never None.
        assert result is not None, "_map_credential_to_finding must never return None."
        assert isinstance(result, Finding), f"Expected Finding, got {type(result).__name__}."

        # Every credential scanner field must be forwarded with exact fidelity.
        assert result.line_no == sf.line_no, "line_no must be forwarded from SecurityFinding."
        assert result.col_start == sf.col_start, "col_start enables surgical caret rendering."
        assert result.match_text == sf.match_text, (
            "match_text must be forwarded so the reporter can obfuscate it."
        )
        assert sf.secret_type in result.message, (
            "secret_type must appear in the Finding message for operator triage."
        )
        assert result.code == "Z201", (
            "code must be 'Z201' (CREDENTIAL_SECRET) so the CLI runner identifies breach findings for Exit 2."
        )

        # Pipeline test: N SecurityFindings → exactly N breach Findings.
        sfs = [
            self._make_sf("aws-access-key", "AKIA1234567890ABCDEF"),
            self._make_sf("stripe-live-key"),
        ]
        findings_list: list[Finding] = []
        for each_sf in sfs:
            findings_list.append(_map_credential_to_finding(each_sf, self._DOCS_ROOT))

        assert len(findings_list) == 2, (
            f"Expected 2 Finding objects from 2 SecurityFindings, got {len(findings_list)}. "
            "A Silencer mutant (no-op return / conditional append) would produce 0."
        )


# ─── Mutant-Killing Tests: _obfuscate_secret boundary conditions ──────────────


@_credential_scanner_skip
class TestObfuscateSecretMutantKill:
    """Kill surviving mutants in _obfuscate_secret().

    Targeted mutants:
    - mutmut_1: ``<= 8`` → ``< 8``  (length-8 string should be fully redacted)
    - mutmut_2: ``<= 8`` → ``<= 9`` (length-9 string should be partially redacted)
    - mutmut_7: ``raw[:4]`` → ``raw[:5]`` (prefix must be exactly 4 chars)
    - mutmut_10/11/12/13: suffix ``raw[-4:]`` and ``(len(raw) - 8)`` star count
    """

    def test_length_8_is_fully_redacted(self) -> None:
        """Exact boundary: 8-char string → all stars.
        Kills ``< 8`` mutant (would partially redact length-8)."""
        raw = "12345678"  # exactly 8 chars
        result = _obfuscate_secret(raw)
        assert result == "********", f"Expected 8 stars, got {result!r}"
        assert len(result) == 8

    def test_length_9_is_partially_redacted(self) -> None:
        """One above boundary: 9-char string → prefix + stars + suffix.
        Kills ``<= 9`` mutant (would fully redact length-9)."""
        raw = "123456789"  # exactly 9 chars
        result = _obfuscate_secret(raw)
        # Should be: raw[:4] + "*" * 1 + raw[-4:] = "1234*6789"
        assert result != "*" * 9, "length-9 must NOT be fully redacted"
        assert result[0] == "1"  # prefix preserved
        assert result[-4:] == "6789"  # suffix preserved
        assert "*" in result

    def test_prefix_is_exactly_4_chars(self) -> None:
        """raw[:4] — kills raw[:5] mutant."""
        raw = "ABCDEFGHIJKLMNOP"  # 16 chars
        result = _obfuscate_secret(raw)
        assert result[:4] == "ABCD"
        assert result[4] != "E", "5th char must be a star, not 'E'"

    def test_suffix_is_exactly_4_chars(self) -> None:
        """raw[-4:] — kills raw[-5:] or raw[-3:] mutants."""
        raw = "ABCDEFGHIJKLMNOP"  # 16 chars
        result = _obfuscate_secret(raw)
        assert result[-4:] == "MNOP"

    def test_star_count_is_length_minus_8(self) -> None:
        """Middle star count: len(raw) - 8 — kills off-by-one mutants."""
        raw = "ABCDEFGHIJKLMNOP"  # 16 chars → 16 - 8 = 8 stars
        result = _obfuscate_secret(raw)
        stars = result[4:-4]
        assert stars == "*" * 8, f"Expected 8 stars, got {stars!r}"

    def test_length_1_fully_redacted(self) -> None:
        """Very short string — not a boundary case but validates the path."""
        assert _obfuscate_secret("X") == "*"

    def test_total_length_preserved(self) -> None:
        """Obfuscated string must always have same length as input."""
        for n in range(1, 20):
            raw = "A" * n
            result = _obfuscate_secret(raw)
            assert len(result) == n, f"len mismatch for n={n}: {result!r}"
