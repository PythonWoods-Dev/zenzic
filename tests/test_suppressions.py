# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Strict suppression-parser contract tests (ADR-063).

Verifies that _is_suppressed accepts only the exact ``zenzic:ignore:``
directive — for both HTML (Markdown) and JSX (MDX) comment formats — and
rejects all syntactic deviations without exception.

Also covers the Z603 DEAD_SUPPRESSION lifecycle (SuppressionTracker) with
three mandatory TDD scenarios mandated by the Architecture Governance Board:

  A. Valid link + dead directive  → no Z101, Z603 fires (suppression wasted).
  B. Broken link + used directive → no Z101, no Z603 (directive consumed).
  C. Z201 credential + Z201 directive → Z201 fires (Inviolability Law),
     Z603 fires (directive was invalid, never consumed).
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core.rules import _is_suppressed
from zenzic.core.suppressions import SuppressionTracker


# ---------------------------------------------------------------------------
# HTML / Markdown format  (<!-- zenzic:ignore: ZXXX -->)
# ---------------------------------------------------------------------------


class TestHtmlSuppressionStrictness:
    def test_positive_strict_match(self) -> None:
        line = "OldBrand was the codename. <!-- zenzic:ignore: Z601 - historical -->"
        assert _is_suppressed(line, "Z601") is True

    def test_negative_hyphen_fallacy(self) -> None:
        """zenzic-ignore (hyphen) must NOT be recognised as a suppression."""
        line = "OldBrand was the codename. <!-- zenzic-ignore: Z601 - historical -->"
        assert _is_suppressed(line, "Z601") is False

    def test_negative_missing_colon_after_ignore(self) -> None:
        """Omitting the colon after 'ignore' must NOT suppress."""
        line = "OldBrand was the codename. <!-- zenzic:ignore Z601 -->"
        assert _is_suppressed(line, "Z601") is False

    def test_negative_typo_in_keyword(self) -> None:
        """A typo in the directive keyword must NOT suppress."""
        line = "OldBrand was the codename. <!-- zenzic:ignor: Z601 -->"
        assert _is_suppressed(line, "Z601") is False


# ---------------------------------------------------------------------------
# JSX / MDX format  ({/* zenzic:ignore: ZXXX */})
# ---------------------------------------------------------------------------


class TestJsxSuppressionStrictness:
    def test_positive_strict_match(self) -> None:
        line = "OldBrand was the codename. {/* zenzic:ignore: Z601 - historical */}"
        assert _is_suppressed(line, "Z601") is True

    def test_negative_hyphen_fallacy(self) -> None:
        """zenzic-ignore (hyphen) inside JSX wrapper must NOT suppress."""
        line = "OldBrand was the codename. {/* zenzic-ignore: Z601 - historical */}"
        assert _is_suppressed(line, "Z601") is False

    def test_negative_wrong_comment_type(self) -> None:
        """Single-line JSX comment ({// ...}) must NOT suppress."""
        line = "OldBrand was the codename. {// zenzic:ignore: Z601 }"
        assert _is_suppressed(line, "Z601") is False

    def test_negative_malformed_closing(self) -> None:
        """Malformed closing (*} instead of */}) must NOT suppress."""
        line = "OldBrand was the codename. {/* zenzic:ignore: Z601 *}"
        assert _is_suppressed(line, "Z601") is False


# ---------------------------------------------------------------------------
# Z603 DEAD_SUPPRESSION — SuppressionTracker lifecycle contract
# ---------------------------------------------------------------------------
#
# These three scenarios are the mandatory TDD suite for Z603.
# They exercise the full suppression lifecycle:
#   parse → is_suppressed (consume) → get_dead_suppressions (Z603)
# ---------------------------------------------------------------------------

_FILE = Path("docs/page.md")


class TestZ603DeadSuppression:
    """Z603 DEAD_SUPPRESSION mandatory TDD scenarios (Architecture Governance)."""

    # ── Scenario A ────────────────────────────────────────────────────────────
    # Valid link + dead directive → no Z101 suppression consumed,
    # Z603 fires because the directive was never matched.
    # ─────────────────────────────────────────────────────────────────────────

    def test_a_valid_link_dead_directive_emits_z603(self) -> None:
        """Scenario A: directive exists but no Z101 was ever suppressed → Z603.

        Simulates a file where a developer added:
            [link](./real-page.md) <!-- zenzic:ignore: Z101 - just in case -->

        The link is valid, so no Z101 finding is produced by the rule engine.
        The directive is therefore never consumed.  Z603 must fire.
        """
        # File text: line 1 has a suppression directive for Z101.
        # No Z101 finding will be produced (link is valid — not emitted here).
        text = "[Real Page](./real-page.md) <!-- zenzic:ignore: Z101 - precaution -->"
        tracker = SuppressionTracker(_FILE, text)

        # Simulate: the rule engine produces ZERO Z101 findings for this file.
        # Therefore is_suppressed is never called for Z101 → directive unconsumed.
        assert len(tracker.directives) == 1
        assert tracker.directives[0].code == "Z101"
        assert tracker.directives[0].consumed is False

        dead = tracker.get_dead_suppressions()

        # Z603 must be emitted for the dead directive.
        assert len(dead) == 1
        assert dead[0].rule_id == "Z603"
        assert dead[0].line_no == 1
        assert dead[0].severity == "warning"
        assert "dead" in dead[0].message.lower()

    # ── Scenario B ────────────────────────────────────────────────────────────
    # Broken link + active directive → Z101 suppressed (consumed),
    # no Z603 (directive was legitimately used).
    # ─────────────────────────────────────────────────────────────────────────

    def test_b_broken_link_directive_consumed_no_z603(self) -> None:
        """Scenario B: Z101 suppressed by directive → consumed, Z603 must NOT fire.

        Simulates a file where a developer added:
            [broken](./missing.md) <!-- zenzic:ignore: Z101 - known broken -->

        The link IS broken, so the rule engine produces a Z101 finding at line 1.
        The tracker.is_suppressed() call marks the directive as consumed.
        No Z603 should be emitted.
        """
        text = "[Broken](./missing.md) <!-- zenzic:ignore: Z101 - known broken -->"
        tracker = SuppressionTracker(_FILE, text)

        # Simulate rule engine producing Z101 at line 1.
        suppressed = tracker.is_suppressed(line_no=1, code="Z101")

        assert suppressed is True
        assert tracker.directives[0].consumed is True

        dead = tracker.get_dead_suppressions()

        # No Z603: the directive was legitimately consumed.
        assert dead == []

    # ── Scenario C ────────────────────────────────────────────────────────────
    # Security code Z201 + Z201 directive → Z201 still fires (Inviolability Law),
    # directive is never consumed (Z201 is non-suppressible), Z603 fires.
    # ─────────────────────────────────────────────────────────────────────────

    def test_c_security_code_inviolability_and_z603(self) -> None:
        """Scenario C: Z201 is non-suppressible → is_suppressed always False,
        directive never consumed → Z603 fires.

        This is the Inviolability Law: security codes (Z201, Z202, Z203, Z204)
        are never suppressible.  If a developer adds:
            AKIA... <!-- zenzic:ignore: Z201 - expected key -->

        Zenzic MUST still emit Z201 (credential scanner fires unconditionally).
        Because is_suppressed("Z201") returns False, the directive is never
        marked consumed, so Z603 must also fire to punish the phantom comment.
        """
        text = "aws_key = AKIAIOSFODNN7EXAMPLE <!-- zenzic:ignore: Z201 - expected -->"
        tracker = SuppressionTracker(_FILE, text)

        # The directive is parsed (it is syntactically valid).
        assert len(tracker.directives) == 1
        assert tracker.directives[0].code == "Z201"

        # Inviolability Law: is_suppressed MUST return False for Z201.
        suppressed = tracker.is_suppressed(line_no=1, code="Z201")
        assert suppressed is False

        # The directive is therefore unconsumed.
        assert tracker.directives[0].consumed is False

        # Z603 fires: the Z201 suppression comment is dead (it never suppressed
        # anything) and must itself be reported as phantom debt.
        dead = tracker.get_dead_suppressions()
        assert len(dead) == 1
        assert dead[0].rule_id == "Z603"
        assert dead[0].line_no == 1


# ---------------------------------------------------------------------------
# SuppressionTracker parsing contract
# ---------------------------------------------------------------------------


class TestSuppressionTrackerParsing:
    """Unit tests for SuppressionTracker._parse() fence-awareness (ADR-084)."""

    def test_directive_inside_fence_is_ignored(self) -> None:
        """Directives inside fenced code blocks must NOT be registered."""
        text = (
            "Normal line.\n```\n<!-- zenzic:ignore: Z505 - this is inside a code block -->\n```\n"
        )
        tracker = SuppressionTracker(_FILE, text)
        assert tracker.directives == []

    def test_directive_in_inline_code_is_ignored(self) -> None:
        """Directives inside backtick inline code spans must NOT be registered (ADR-084)."""
        text = "Use `<!-- zenzic:ignore: Z505 -->` to suppress Z505 on a line."
        tracker = SuppressionTracker(_FILE, text)
        assert tracker.directives == []

    def test_multiple_directives_on_same_line(self) -> None:
        """Two directives on one line are registered as two independent entries."""
        text = "line <!-- zenzic:ignore: Z107 - a --> and <!-- zenzic:ignore: Z505 - b -->"
        tracker = SuppressionTracker(_FILE, text)
        assert len(tracker.directives) == 2
        codes = {d.code for d in tracker.directives}
        assert codes == {"Z107", "Z505"}

    def test_directive_on_line_two(self) -> None:
        """Line numbers are 1-based and correct for multi-line documents."""
        text = "First line.\nSecond line. <!-- zenzic:ignore: Z601 - hist -->"
        tracker = SuppressionTracker(_FILE, text)
        assert len(tracker.directives) == 1
        assert tracker.directives[0].line_no == 2

    def test_no_directives_plain_text(self) -> None:
        """A plain text file with no directives produces an empty registry."""
        tracker = SuppressionTracker(_FILE, "Hello world.\nNothing here.\n")
        assert tracker.directives == []

    def test_count_inline_suppressions_compatibility(self) -> None:
        """count_inline_suppressions() matches the number of registered directives."""
        from zenzic.core.suppressions import count_inline_suppressions

        text = (
            "line1 <!-- zenzic:ignore: Z101 -->\n"
            "line2 <!-- zenzic:ignore: Z505 -->\n"
            "```\n"
            "<!-- zenzic:ignore: Z601 - inside fence, ignored -->\n"
            "```\n"
        )
        tracker = SuppressionTracker(_FILE, text)
        assert count_inline_suppressions(text) == len(tracker.directives) == 2


def test_global_usage_tracker_toml_line_resolution(tmp_path: Path) -> None:
    """Verify that Z620 findings report the actual line number in .zenzic.toml."""
    from zenzic.core.suppressions import GlobalUsageTracker
    from zenzic.models.config import GovernanceConfig, ZenzicConfig

    toml_path = tmp_path / ".zenzic.toml"
    toml_path.write_text(
        "[governance]\n"
        "directory_policies = {\n"
        '    "docs/assets/**" = ["Z405"],\n'
        '    "docs/blog/**" = ["Z405"]\n'
        "}\n",
        encoding="utf-8",
    )

    config = ZenzicConfig(
        governance=GovernanceConfig(
            directory_policies={
                "docs/assets/**": ["Z405"],
                "docs/blog/**": ["Z405"],
            }
        )
    )
    config.origin_file = toml_path

    tracker = GlobalUsageTracker(config)
    stale = tracker.get_stale_findings(check_all=True)

    lines_by_pattern = {f.message: f.line_no for f in stale}
    assert any(
        "docs/assets/**" in msg and line_no == 3 for msg, line_no in lines_by_pattern.items()
    )
    assert any("docs/blog/**" in msg and line_no == 4 for msg, line_no in lines_by_pattern.items())


def test_global_usage_tracker_topology_policy_pair_consumption() -> None:
    """Using either topological code must consume the paired directory policy family."""
    from zenzic.core.suppressions import GlobalUsageTracker
    from zenzic.models.config import GovernanceConfig, ZenzicConfig

    config = ZenzicConfig(
        governance=GovernanceConfig(directory_policies={"docs/historical/**": ["Z410", "Z411"]})
    )
    tracker = GlobalUsageTracker(config)

    tracker.mark_directory_policy_used("docs/historical/**", "Z411")

    assert ("docs/historical/**", "Z410") not in tracker.unused_dir_policies
    assert ("docs/historical/**", "Z411") not in tracker.unused_dir_policies
