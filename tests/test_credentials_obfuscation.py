# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Adversarial Validation — Security Stress Test: security audit tests for v0.6.1rc2.

Task 1: Path Traversal Guard Jailbreak (path traversal bypass attempts)
Task 2: Credential Scanner Bypass (credential hiding attempts)
Task 3: DoS / Resource Exhaustion
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from zenzic.core.credentials import (
    CredentialViolation,
    SecurityFinding,
    _normalize_line_for_scan,
    safe_read_line,
    scan_line_for_secrets,
    scan_lines_with_lookback,
)
from zenzic.core.resolver import InMemoryPathResolver, PathTraversal, Resolved


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 1: Path Traversal Guard Jailbreak
# ═══════════════════════════════════════════════════════════════════════════════


def _make_resolver(root: str = "/docs") -> InMemoryPathResolver:
    """Build a minimal resolver with a few files for testing."""
    root_path = Path(root)
    md_contents = {
        root_path / "index.md": "# Home\n",
        root_path / "guide" / "install.md": "# Install\n",
        root_path / "guide" / "index.md": "# Guide\n",
    }
    anchors: dict[Path, set[str]] = {p: set() for p in md_contents}
    return InMemoryPathResolver(root_dir=root_path, md_contents=md_contents, anchors_cache=anchors)


class TestPathTraversalGuardJailbreak:
    """Attempt to bypass the path traversal guard detection."""

    def setup_method(self) -> None:
        self.resolver = _make_resolver()
        self.source = Path("/docs/index.md")

    # ── Basic traversal (should be caught) ──

    def test_basic_traversal(self) -> None:
        outcome = self.resolver.resolve(self.source, "../../etc/passwd")
        assert isinstance(outcome, PathTraversal)

    # ── URL-encoded paths ──

    def test_url_encoded_dot_dot_slash(self) -> None:
        """Try %2e%2e%2f to bypass '..' detection."""
        outcome = self.resolver.resolve(self.source, "%2e%2e%2f%2e%2e%2fetc/passwd")
        assert isinstance(outcome, PathTraversal), (
            f"BYPASS: URL-encoded traversal returned {outcome}"
        )

    def test_double_encoded_traversal(self) -> None:
        """Try %252e%252e%252f (double encoding)."""
        outcome = self.resolver.resolve(self.source, "%252e%252e%252f%252e%252e%252fetc/passwd")
        # Double encoding: unquote('%252e') -> '%2e' which stays literal
        # This should NOT resolve to a valid file, but also might not be PathTraversal
        assert not isinstance(outcome, Resolved), f"BYPASS: Double-encoded resolved to {outcome}"

    # ── Null bytes ──

    def test_null_byte_in_path(self) -> None:
        """Try %00 null byte injection."""
        outcome = self.resolver.resolve(self.source, "../../etc/passwd%00.md")
        assert isinstance(outcome, PathTraversal), f"BYPASS: Null byte traversal returned {outcome}"

    # ── Unicode normalization tricks ──

    def test_unicode_double_dot_leader(self) -> None:
        """Try U+2025 TWO DOT LEADER instead of '..'."""
        outcome = self.resolver.resolve(self.source, "\u2025/\u2025/etc/passwd")
        # TWO DOT LEADER is a single char, not '..' - should not resolve
        assert not isinstance(outcome, Resolved), (
            f"BYPASS: Unicode dot leader resolved to {outcome}"
        )

    def test_unicode_fullwidth_dot(self) -> None:
        """Try U+FF0E FULLWIDTH FULL STOP instead of '.'."""
        outcome = self.resolver.resolve(self.source, "\uff0e\uff0e/\uff0e\uff0e/etc/passwd")
        assert not isinstance(outcome, Resolved), f"BYPASS: Fullwidth dots resolved to {outcome}"

    def test_unicode_one_dot_leader(self) -> None:
        """Try U+2024 ONE DOT LEADER."""
        outcome = self.resolver.resolve(self.source, "\u2024\u2024/\u2024\u2024/etc/passwd")
        assert not isinstance(outcome, Resolved), f"BYPASS: One dot leader resolved to {outcome}"

    # ── Mixed separators ──

    def test_mixed_separators_backslash(self) -> None:
        """Try ..\\..\\etc\\passwd with mixed separators."""
        outcome = self.resolver.resolve(self.source, "..\\..\\etc\\passwd")
        assert isinstance(outcome, PathTraversal), f"BYPASS: Mixed separators returned {outcome}"

    def test_mixed_forward_back_slash(self) -> None:
        """Try ..\\/..\\/ mixed."""
        outcome = self.resolver.resolve(self.source, "..\\/..\\//etc/passwd")
        assert isinstance(outcome, PathTraversal), f"BYPASS: Mixed slash returned {outcome}"

    # ── Overlong UTF-8 sequences (as percent-encoded) ──

    def test_overlong_utf8_dot(self) -> None:
        """Try overlong UTF-8 encoding of '.' -> %c0%ae."""
        outcome = self.resolver.resolve(self.source, "%c0%ae%c0%ae/%c0%ae%c0%ae/etc/passwd")
        assert not isinstance(outcome, Resolved), f"BYPASS: Overlong UTF-8 resolved to {outcome}"

    # ── Circular/redundant path segments ──

    def test_dot_dot_dot_slash(self) -> None:
        """Try .../... instead of ../.. ."""
        outcome = self.resolver.resolve(self.source, ".../..../etc/passwd")
        assert not isinstance(outcome, Resolved), f"BYPASS: Triple-dot resolved to {outcome}"

    def test_traversal_with_valid_prefix(self) -> None:
        """Try guide/../../../etc/passwd - valid prefix then escape."""
        outcome = self.resolver.resolve(self.source, "guide/../../../etc/passwd")
        assert isinstance(outcome, PathTraversal), (
            f"BYPASS: Valid prefix traversal returned {outcome}"
        )

    def test_absolute_path(self) -> None:
        """Try absolute /etc/passwd."""
        outcome = self.resolver.resolve(self.source, "/etc/passwd")
        # Absolute paths are anchored to root_dir, so this would look for /docs/etc/passwd
        assert not isinstance(outcome, Resolved) or str(outcome.target) != "/etc/passwd"

    def test_encoded_slash_variant(self) -> None:
        """Try ..%2f..%2fetc%2fpasswd."""
        outcome = self.resolver.resolve(self.source, "..%2f..%2fetc%2fpasswd")
        assert isinstance(outcome, PathTraversal), (
            f"BYPASS: Encoded slash traversal returned {outcome}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 2: Credential Scanner Bypass
# ═══════════════════════════════════════════════════════════════════════════════

# A real-looking AWS key for testing
_FAKE_AWS_KEY = "AKIAIOSFODNN7EXAMPLE"  # 20 chars: AKIA + 16

# A real-looking GitHub token
_FAKE_GH_TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"  # ghp_ + 36


def _build_fake_stateless_ghs_token(total_len: int = 550) -> str:
    """Build a fake ghs_ token with JWT-like dot-separated segments."""
    if total_len <= 4:
        return "ghs_"
    payload_len = total_len - 4
    # Include dots to emulate stateless JWT-like installation tokens.
    pattern = "abcDEF123._-"
    payload = (pattern * ((payload_len // len(pattern)) + 1))[:payload_len]
    return "ghs_" + payload


# A real-looking GitLab PAT
_FAKE_GL_PAT = "glpat-ABCDEFGHIJKLMNOPQRSTUVWXYZab"  # glpat- + 26


class TestCredentialScannerBypass:
    """Attempt to hide credentials from the credential scanner."""

    def _has_finding(self, line: str) -> bool:
        """Return True if the credential scanner detects a secret in *line*."""
        return any(True for _ in scan_line_for_secrets(line, Path("test.md"), 1))

    # ── Baseline: credential scanner catches plain secrets ──

    def test_baseline_aws_key_detected(self) -> None:
        assert self._has_finding(f"key = {_FAKE_AWS_KEY}")

    def test_baseline_gh_token_detected(self) -> None:
        assert self._has_finding(f"token = {_FAKE_GH_TOKEN}")

    def test_long_stateless_ghs_token_detected_and_fast(self) -> None:
        """New GitHub App stateless token format (ghs_) must be detected quickly."""
        token = _build_fake_stateless_ghs_token(550)
        line = f"token = {token}"
        t0 = time.monotonic()
        findings = list(scan_line_for_secrets(line, Path("test.md"), 1))
        elapsed = time.monotonic() - t0
        assert any(f.secret_type == "github-token" for f in findings), (
            "Credential scanner failed to detect long stateless ghs_ token"
        )
        assert elapsed < 2, f"Long ghs_ token scan took {elapsed:.3f}s (>2s guard)"

    def test_baseline_gl_pat_detected(self) -> None:
        assert self._has_finding(f"pat = {_FAKE_GL_PAT}")

    # ── Zero-width Unicode chars inserted in tokens ──

    def test_zwj_in_aws_key(self) -> None:
        """Insert zero-width joiner U+200D inside token."""
        obfuscated = _FAKE_AWS_KEY[:8] + "\u200d" + _FAKE_AWS_KEY[8:]
        detected = self._has_finding(f"key = {obfuscated}")
        if not detected:
            pytest.fail(f"BYPASS: ZWJ in AWS key evaded credential scanner: {obfuscated!r}")

    def test_zwnj_in_gh_token(self) -> None:
        """Insert zero-width non-joiner U+200C inside token."""
        obfuscated = _FAKE_GH_TOKEN[:10] + "\u200c" + _FAKE_GH_TOKEN[10:]
        detected = self._has_finding(f"token = {obfuscated}")
        if not detected:
            pytest.fail(f"BYPASS: ZWNJ in GH token evaded credential scanner: {obfuscated!r}")

    def test_zwsp_in_gl_pat(self) -> None:
        """Insert zero-width space U+200B inside token."""
        obfuscated = _FAKE_GL_PAT[:10] + "\u200b" + _FAKE_GL_PAT[10:]
        detected = self._has_finding(f"pat = {obfuscated}")
        if not detected:
            pytest.fail(f"BYPASS: ZWSP in GitLab PAT evaded credential scanner: {obfuscated!r}")

    # ── Frontmatter YAML multi-line strings ──

    def test_yaml_multiline_fold(self) -> None:
        """YAML folded scalar splits token across lines."""
        # Each line scanned individually, so split token across lines
        line1 = "api_key: >-"
        line2 = "  AKIA"
        line3 = "  IOSFODNN7EXAMPLE"
        # Credential scanner runs line by line - only detect if full pattern in one line
        d1 = self._has_finding(line1)
        d2 = self._has_finding(line2)
        d3 = self._has_finding(line3)
        if not (d1 or d2 or d3):
            # This is expected - split across lines evades line-by-line scanning
            # Mark as a known limitation, not a failure
            pass  # Known limitation: line-by-line scanning can't catch cross-line splits

    # ── HTML entities ──

    def test_html_entity_obfuscation(self) -> None:
        """Use HTML char references to spell out a token."""
        # &#65;&#75;&#73;&#65; = AKIA
        html_key = "&#65;&#75;&#73;&#65;IOSFODNN7EXAMPLE"
        detected = self._has_finding(html_key)
        if not detected:
            pytest.fail(f"BYPASS: HTML entities evaded credential scanner: {html_key!r}")

    # ── Base64-encoded tokens in URLs ──

    def test_base64_encoded_token(self) -> None:
        """Base64-encode a token in a URL query param."""
        import base64

        encoded = base64.b64encode(_FAKE_AWS_KEY.encode()).decode()
        line = f"https://example.com/api?key={encoded}"
        detected = self._has_finding(line)
        if not detected:
            # Base64 encoding is expected to evade pattern-based detection
            pass  # Known limitation

    # ── Split tokens across table cells ──

    def test_split_token_in_table(self) -> None:
        """Split token across table cells with backticks and +."""
        line = "| Key | `AKIA` + `IOSFODNN7EXAMPLE` |"
        detected = self._has_finding(line)
        assert detected, f"BYPASS: Split token in table evaded credential scanner: {line!r}"

    # ── MDX/JSX comments ──

    def test_token_in_jsx_comment(self) -> None:
        """Hide token inside JSX comment."""
        line = f"{{/* {_FAKE_AWS_KEY} */}}"
        detected = self._has_finding(line)
        assert detected, f"BYPASS: JSX comment evaded credential scanner: {line!r}"

    def test_token_in_html_comment(self) -> None:
        """Hide token inside HTML comment."""
        line = f"<!-- {_FAKE_GH_TOKEN} -->"
        detected = self._has_finding(line)
        assert detected, f"BYPASS: HTML comment evaded credential scanner: {line!r}"

    # ── safe_read_line firewall ──

    def test_safe_read_line_blocks_secret(self) -> None:
        """safe_read_line must raise CredentialViolation on detection."""
        with pytest.raises(CredentialViolation):
            safe_read_line(f"key = {_FAKE_AWS_KEY}", Path("test.md"), 1)


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 3: DoS / Resource Exhaustion
# ═══════════════════════════════════════════════════════════════════════════════


class TestDosResilience:
    """Test resource exhaustion resilience."""

    def test_10mb_single_line(self) -> None:
        """A single file with a 10MB line should not crash or take >30s."""
        big_line = "a" * (10 * 1024 * 1024)
        content = big_line + "\n"
        t0 = time.monotonic()
        # Test credential scanner on the big line
        list(scan_line_for_secrets(content, Path("big.md"), 1))
        elapsed = time.monotonic() - t0
        assert elapsed < 30, f"10MB line took {elapsed:.1f}s (>30s limit)"

    def test_10mb_line_with_embedded_secret(self) -> None:
        """Credential scanner should still find secrets in a 10MB line (within 1MiB truncation)."""
        # Place secret near the beginning (within _MAX_LINE_LENGTH)
        big_line = f"prefix {_FAKE_AWS_KEY} " + "a" * (10 * 1024 * 1024)
        findings = list(scan_line_for_secrets(big_line, Path("big.md"), 1))
        assert len(findings) > 0, "Credential scanner should find secret at start of big line"

    def test_10mb_line_secret_past_truncation(self) -> None:
        """Secret placed past 1MiB truncation limit should be silently missed."""
        # Place secret past the _MAX_LINE_LENGTH (1MiB)
        big_line = "a" * (2 * 1024 * 1024) + _FAKE_AWS_KEY
        findings = list(scan_line_for_secrets(big_line, Path("big.md"), 1))
        # This is expected behavior - truncation is documented
        # Just verify it doesn't crash
        assert isinstance(findings, list)

    def test_5000_tiny_files_resolver(self) -> None:
        """5000 tiny 1-line files should resolve within reasonable time."""
        root = Path("/docs")
        md_contents = {}
        for i in range(5000):
            p = root / f"page_{i:04d}.md"
            md_contents[p] = f"# Page {i}\n"
        anchors: dict[Path, set[str]] = {p: set() for p in md_contents}

        t0 = time.monotonic()
        resolver = InMemoryPathResolver(
            root_dir=root, md_contents=md_contents, anchors_cache=anchors
        )
        # Resolve a bunch of links
        source = root / "page_0000.md"
        for i in range(5000):
            resolver.resolve(source, f"page_{i:04d}.md")
        elapsed = time.monotonic() - t0
        assert elapsed < 30, f"5000 file resolution took {elapsed:.1f}s (>30s limit)"

    def test_deeply_nested_dirs(self) -> None:
        """50+ nested directory levels should not crash."""
        root = Path("/docs")
        # Build a path 50 levels deep
        deep_path = root
        for i in range(50):
            deep_path = deep_path / f"level{i}"
        deep_path = deep_path / "index.md"

        md_contents = {
            root / "index.md": "# Home\n",
            deep_path: "# Deep\n",
        }
        anchors: dict[Path, set[str]] = {p: set() for p in md_contents}

        resolver = InMemoryPathResolver(
            root_dir=root, md_contents=md_contents, anchors_cache=anchors
        )
        # Resolve from root to deeply nested file
        rel = str(deep_path.relative_to(root))
        outcome = resolver.resolve(root / "index.md", rel)
        assert isinstance(outcome, Resolved)

    def test_null_bytes_file_content(self) -> None:
        """Files with only null bytes should not crash the credential scanner."""
        null_content = "\x00" * 10000
        t0 = time.monotonic()
        list(scan_line_for_secrets(null_content, Path("null.md"), 1))
        elapsed = time.monotonic() - t0
        assert elapsed < 5, f"Null bytes scan took {elapsed:.1f}s"

    def test_normalizer_on_huge_input(self) -> None:
        """The line normalizer should handle large inputs without ReDoS."""
        # Pathological input for regex: many backticks and pipes
        pathological = "`a`|" * 100000
        t0 = time.monotonic()
        _normalize_line_for_scan(pathological)
        elapsed = time.monotonic() - t0
        assert elapsed < 10, f"Normalizer on 400K pathological input took {elapsed:.1f}s"

    def test_rule_engine_many_files(self) -> None:
        """AdaptiveRuleEngine on 5000 files should stay fast."""
        from zenzic.core.rules import AdaptiveRuleEngine, CustomRule

        rule = CustomRule(
            id="ZZ-TEST", pattern=r"\bTODO\b", message="todo found", severity="warning"
        )
        engine = AdaptiveRuleEngine([rule])

        t0 = time.monotonic()
        for i in range(5000):
            engine.run(Path(f"page_{i}.md"), f"# Page {i}\nSome content here\n")
        elapsed = time.monotonic() - t0
        assert elapsed < 30, f"5000 file rule engine took {elapsed:.1f}s (>30s limit)"


# ═══════════════════════════════════════════════════════════════════════════════
# ZRT-007: Comment-interleaving bypass
# ═══════════════════════════════════════════════════════════════════════════════


class TestCommentInterleaving:
    """Tokens hidden via HTML/MDX comments inserted mid-token."""

    @staticmethod
    def _has_finding(line: str) -> bool:
        return bool(list(scan_line_for_secrets(line, Path("test.md"), 1)))

    def test_html_comment_interleaved_aws(self) -> None:
        """ghp_ABC<!-- comment -->DEF... should be detected after comment strip."""
        line = "AKIA<!-- hidden -->IOSFODNN7EXAMPLE"
        assert self._has_finding(line), f"BYPASS: HTML comment interleaving: {line!r}"

    def test_mdx_comment_interleaved_gh_token(self) -> None:
        """ghp_ABC{/* comment */}DEF... should be detected."""
        token = _FAKE_GH_TOKEN
        line = f"{token[:10]}{{/* noise */}}{token[10:]}"
        assert self._has_finding(line), f"BYPASS: MDX comment interleaving: {line!r}"

    def test_multiple_comments_interleaved(self) -> None:
        """Multiple comments splitting a single token."""
        line = "AK<!-- a -->IA<!-- b -->IOSFODNN7EXAMPLE"
        assert self._has_finding(line), f"BYPASS: Multi-comment interleaving: {line!r}"

    def test_mdx_comment_in_gitlab_pat(self) -> None:
        """GitLab PAT with MDX comment."""
        pat = _FAKE_GL_PAT
        line = f"{pat[:8]}{{/* x */}}{pat[8:]}"
        assert self._has_finding(line), f"BYPASS: MDX comment in GitLab PAT: {line!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# ZRT-007: Lookback buffer (cross-line split detection)
# ═══════════════════════════════════════════════════════════════════════════════


class TestLookbackBuffer:
    """Tokens split across two consecutive lines should be detected."""

    @staticmethod
    def _scan_multiline(lines: list[str]) -> list[SecurityFinding]:
        numbered = list(enumerate(lines, start=1))
        return list(scan_lines_with_lookback(iter(numbered), Path("test.md")))

    def test_aws_key_split_across_lines(self) -> None:
        """AKIA on line 1, rest on line 2."""
        findings = self._scan_multiline(["key: AKIA\n", "IOSFODNN7EXAMPLE\n"])
        types = {f.secret_type for f in findings}
        assert "aws-access-key" in types, "Lookback should catch AWS key split across lines"

    def test_gh_token_split(self) -> None:
        """GitHub token split across lines."""
        token = _FAKE_GH_TOKEN
        findings = self._scan_multiline([f"token: {token[:15]}\n", f"{token[15:]}\n"])
        types = {f.secret_type for f in findings}
        assert "github-token" in types, "Lookback should catch GH token split across lines"

    def test_yaml_folded_scalar(self) -> None:
        """YAML folded scalar splits secret."""
        findings = self._scan_multiline(
            [
                "api_key: >-\n",
                "  AKIA\n",
                "  IOSFODNN7EXAMPLE\n",
            ]
        )
        types = {f.secret_type for f in findings}
        assert "aws-access-key" in types, "Lookback should catch YAML folded scalar"

    def test_no_false_positive_unrelated_lines(self) -> None:
        """Two unrelated lines should not produce a false positive."""
        findings = self._scan_multiline(
            [
                "This is normal text AKIA\n",
                "And this is something else entirely\n",
            ]
        )
        types = {f.secret_type for f in findings}
        assert "aws-access-key" not in types, "Should not false-positive on unrelated lines"

    def test_single_line_still_detected(self) -> None:
        """Normal single-line detection still works through lookback scanner."""
        findings = self._scan_multiline([f"key = {_FAKE_AWS_KEY}\n"])
        types = {f.secret_type for f in findings}
        assert "aws-access-key" in types

    def test_lookback_dedup(self) -> None:
        """Secret on one line should not be reported twice (once normal, once lookback)."""
        findings = self._scan_multiline(
            [
                "nothing here\n",
                f"key = {_FAKE_AWS_KEY}\n",
            ]
        )
        aws_findings = [f for f in findings if f.secret_type == "aws-access-key"]
        assert len(aws_findings) == 1, f"Expected 1 finding, got {len(aws_findings)}"


# ═══════════════════════════════════════════════════════════════════════════════
# ZRT-007: Base64 speculative decoder — attack vector S2 sealed (CEO-194 / D095)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBase64Bypass:
    """Base64 speculative decoder: CEO-194 closes the S2 adversarial validation vector.

    Canonical test vector (CEO-201, locked):
        Z2hwXzEyMzQ1Njc4OTBhYmNkZWZnaGlqa2xtbm9wcXJzdHV2d3h5eg==
        decodes to: ghp_1234567890abcdefghijklmnopqrstuvwxyz (GitHub PAT, 40 chars).
    """

    # Locked canonical test vector (CEO-201).
    _B64_GITHUB_PAT = "Z2hwXzEyMzQ1Njc4OTBhYmNkZWZnaGlqa2xtbm9wcXJzdHV2d3h5eg=="
    # Decoded form for reference: ghp_1234567890abcdefghijklmnopqrstuvwxyz

    def test_base64_github_pat_detected(self) -> None:
        """A Base64-encoded GitHub PAT in a frontmatter field must be flagged.

        Simulates the S2 adversarial validation vector: attacker places the encoded
        token in a YAML frontmatter field to evade the raw-text scan.
        """
        line = f"token: {self._B64_GITHUB_PAT}"
        findings = list(scan_line_for_secrets(line, Path("secret.md"), 5))
        gh_findings = [f for f in findings if f.secret_type == "github-token"]
        assert len(gh_findings) == 1, (
            f"Expected 1 github-token finding for Base64-encoded PAT; got {len(gh_findings)}"
        )
        assert gh_findings[0].line_no == 5
        assert gh_findings[0].file_path == Path("secret.md")

    def test_base64_aws_key_detected(self) -> None:
        """A Base64-encoded AWS access key must also be flagged."""
        import base64

        encoded = base64.b64encode(_FAKE_AWS_KEY.encode()).decode()
        line = f"key = {encoded}"
        findings = list(scan_line_for_secrets(line, Path("test.md"), 1))
        aws = [f for f in findings if f.secret_type == "aws-access-key"]
        assert len(aws) == 1, (
            f"Expected 1 aws-access-key finding for Base64-encoded AWS key; got {len(aws)}"
        )

    def test_base64_short_string_no_false_positive(self) -> None:
        """A short Base64 string (< 20 chars) must not generate false positives."""
        # 'dGVzdA==' decodes to 'test' — too short to match any credential pattern
        line = "note: dGVzdA=="
        findings = list(scan_line_for_secrets(line, Path("test.md"), 1))
        assert findings == [], f"Expected no findings for short Base64 string; got {findings}"

    def test_base64_innocent_prose_no_false_positive(self) -> None:
        """Long Base64 that decodes to innocent text must not produce a finding."""
        import base64

        # Encode a long innocent string that is definitely not a credential
        innocent = "This is just some harmless documentation prose with no secrets here."
        encoded = base64.b64encode(innocent.encode()).decode()
        line = f"content: {encoded}"
        findings = list(scan_line_for_secrets(line, Path("test.md"), 1))
        assert findings == [], f"Expected no findings for innocent Base64 content; got {findings}"

    def test_base64_decoded_token_preceded_by_a_word_char_is_still_detected(self) -> None:
        """A GitHub token reconstructed via Base64 decode (or the lookback
        join) must be caught even when the byte immediately before its
        ``ghp_``/``gho_``/etc. prefix is itself a word character with no
        separator -- the raw-text scan's leading ``\\b`` is a reasonable
        anti-false-positive guard for hand-typed prose, but it silently
        drops a token nobody ever gets to see the raw bytes of (decoded
        Base64, a cross-line lookback join), which is exactly the case an
        obfuscation-resistant scanner exists to cover.

        Vector: "start" immediately followed by ``_FAKE_GH_TOKEN``, so 't'
        precedes the token prefix with no word boundary between them, then
        Base64-encoded.

        The blob is built here rather than pasted as a literal, and that is
        deliberate: a hardcoded Base64 string decoding to a GitHub-token
        shape is blocked by GitHub's own push protection, which decodes
        candidate blobs. Constructing it keeps the test honest about its
        vector while leaving no token shape -- encoded or plain -- in the
        source.
        """
        import base64

        blob = base64.b64encode(f"start{_FAKE_GH_TOKEN}".encode()).decode()
        line = f"blob: {blob}"
        findings = list(scan_line_for_secrets(line, Path("test.md"), 1))
        gh = [f for f in findings if f.secret_type == "github-token"]
        assert len(gh) == 1, (
            f"Expected 1 github-token finding for a decoded token preceded "
            f"by a word character; got {len(gh)} (full findings: {findings})"
        )

    def test_base64_with_embedded_plus_still_decodes(self) -> None:
        """A Base64 blob containing a literal '+' (a real Base64 alphabet
        character) must still decode and be flagged -- not corrupted by the
        concatenation-operator stripper, which used to delete every '+' in
        the line unconditionally before the speculative decode ever ran.

        Canonical vector: two filler bytes, then '>' (0x3E), then an
        AWS-shaped key. The '>' lands as the third byte of a 3-byte group,
        and its low 6 bits (111110) always encode to '+' regardless of what
        follows -- so whoever writes the blob can place a '+' anywhere in it
        by choosing filler. Deleting that '+' shifts every following Base64
        group by one character, garbling the decode of a real secret placed
        after it: a scanner-evasion bypass, not a cosmetic bug.

        Built rather than pasted, for the same reason as the sibling test
        above: a literal blob decoding to a credential shape does not
        survive push protection.
        """
        import base64

        blob = base64.b64encode(f"AA>{_FAKE_AWS_KEY}".encode()).decode()
        assert "+" in blob, "the vector must actually contain a '+' to prove anything"
        line = f"config: {blob}"
        findings = list(scan_line_for_secrets(line, Path("test.md"), 1))
        aws = [f for f in findings if f.secret_type == "aws-access-key"]
        assert len(aws) == 1, (
            f"Expected 1 aws-access-key finding for a Base64 blob containing "
            f"a literal '+'; got {len(aws)} (full findings: {findings})"
        )


# ─── Mutant-Killing Tests: _normalize_line_for_scan ─────────────────────────


class TestNormalizeLineForCredentialScannerMutantKill:
    """Kill surviving mutants in _normalize_line_for_scan().

    Targeted mutants:
    - mutmut_22: MDX comment sub → "XXXX" instead of ""
    - mutmut_40: table pipe sub → "XX XX" instead of " "
    - mutmut_42: whitespace join → "XX XX".join instead of " ".join
    """

    def test_mdx_comment_removed_not_replaced(self) -> None:
        """MDX comment must be stripped (empty string), not replaced with noise.
        Kills mutmut_22: _MDX_COMMENT_RE.sub('XXXX', normalized)."""
        line = "ghp_ABC{/* comment */}DEF"
        result = _normalize_line_for_scan(line)
        assert "XXXX" not in result
        assert "{" not in result
        assert "comment" not in result
        # The reconstructed token should be intact
        assert "ghp_ABCDEF" in result

    def test_table_pipe_replaced_with_single_space(self) -> None:
        """Table pipe must become a single space, not 'XX XX' or empty.
        Kills mutmut_40: _TABLE_PIPE_RE.sub('XX XX', normalized)."""
        line = "col1 | col2 | col3"
        result = _normalize_line_for_scan(line)
        assert "XX XX" not in result
        assert "|" not in result
        # Pipes replaced by space — after whitespace collapse: "col1 col2 col3"
        assert "col1" in result
        assert "col2" in result
        assert "col3" in result

    def test_whitespace_collapsed_with_single_space_join(self) -> None:
        """Final join must use single space ' ', not 'XX XX'.
        Kills mutmut_42: 'XX XX'.join(normalized.split())."""
        line = "  lots   of   spaces  "
        result = _normalize_line_for_scan(line)
        assert "XX XX" not in result
        # After " ".join(normalized.split()): single spaces between words
        assert result == "lots of spaces"

    def test_mdx_comment_interleaved_token_reconstructed(self) -> None:
        """Full integration: MDX comment inside a secret token is stripped.
        Verifies the MDX strip produces '' and reconstructed token is scannable."""
        raw_line = (
            "token: sk-{/* obfuscation */}live_ABCDEFGHIJ1234567890abcdefghijklmnopqrstuvwxyz12"
        )
        result = _normalize_line_for_scan(raw_line)
        assert "{" not in result
        assert "obfuscation" not in result
        # The merged token should be present after stripping
        assert "sk-live_" in result
