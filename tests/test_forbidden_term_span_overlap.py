# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A forbidden term must survive sharing a line with a credential.

``ReferenceScanner.harvest()`` ran the credential pass first, collected every
line number that produced a ``Z201`` into ``secret_line_nos``, and then had the
forbidden-term pass skip those lines wholesale::

    if lineno in secret_line_nos:
        continue

So any ``Z204`` sharing a line with a credential was silently dropped — the same
two findings split across two lines reported correctly, which is what made the
behaviour look like a detection gap rather than a deliberate rule.

The skip was not arbitrary. It prevents a second panel for one leak when a
configured forbidden pattern happens to match *inside* the secret itself. That
case is preserved here; only the line-granularity of the suppression changes to
span-granularity.

One subtlety drives the design. ``col_start`` is not always a real offset into
the raw line: ``scan_line_for_secrets`` sets it to ``0`` when a secret was found
only in the *normalised* form of the line ("col position is meaningless after
stripping Markdown noise"), and ``scan_lines_with_lookback`` hardcodes ``0`` for
a match reconstructed across two lines. A bare ``col_start`` of ``0`` is
therefore ambiguous — it can mean "at offset 0" or "position unknown". The
overlap check treats a span as usable only when ``match_text`` genuinely occurs
at ``col_start`` in the raw line, and falls back to suppressing the whole line
when it does not. Conservative in exactly the direction that cannot invent a
duplicate report for a single secret.
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core.scanner import ReferenceScanner
from zenzic.models.config import ZenzicConfig


_SECRET = "AKIAIOSFODNN7EXAMPLE"


def _secret_types(text: str, forbidden: list[str], tmp_path: Path) -> list[str]:
    """Every SECRET event harvest() yields, by ``secret_type``."""
    page = tmp_path / "index.md"
    page.write_text(text, encoding="utf-8")
    config = ZenzicConfig(docs_dir=Path("docs"), forbidden_patterns=forbidden)
    scanner = ReferenceScanner(page, config)
    return [
        data.secret_type
        for _lineno, event_type, data in scanner.harvest(text)
        if event_type == "SECRET"
    ]


class TestNonOverlappingSpansOnOneLine:
    """The defect: two genuinely independent findings sharing a line."""

    def test_term_after_credential_is_reported(self, tmp_path: Path) -> None:
        text = f'aws_key = "{_SECRET}"  # ProjectOmniInternal rollout\n'
        types = _secret_types(text, ["ProjectOmniInternal"], tmp_path)
        assert "FORBIDDEN_TERM" in types, (
            f"Z204 dropped for sharing a line with a credential; got {types}"
        )
        assert "aws-access-key" in types, f"the credential must still report; got {types}"

    def test_term_before_credential_is_reported(self, tmp_path: Path) -> None:
        """Order must not matter."""
        text = f'ProjectOmniInternal uses aws_key = "{_SECRET}"\n'
        types = _secret_types(text, ["ProjectOmniInternal"], tmp_path)
        assert "FORBIDDEN_TERM" in types and "aws-access-key" in types

    def test_term_adjacent_to_the_secret_still_reported(self, tmp_path: Path) -> None:
        """Adjacent but not intersecting: spans touch, they do not overlap."""
        text = f'key="{_SECRET}"ProjectOmniInternal\n'
        types = _secret_types(text, ["ProjectOmniInternal"], tmp_path)
        assert "FORBIDDEN_TERM" in types, f"adjacent spans must not suppress; got {types}"


class TestOverlappingSpansStaySuppressed:
    """The reason the skip existed. This behaviour must not regress."""

    def test_term_inside_the_secret_is_suppressed(self, tmp_path: Path) -> None:
        """A pattern matching within the credential must not double-report it."""
        text = f'aws_key = "{_SECRET}"\n'
        types = _secret_types(text, ["IOSFODNN7"], tmp_path)
        assert "FORBIDDEN_TERM" not in types, (
            f"a term inside the secret produced a second panel for one leak; got {types}"
        )
        assert "aws-access-key" in types

    def test_term_equal_to_the_whole_secret_is_suppressed(self, tmp_path: Path) -> None:
        text = f'aws_key = "{_SECRET}"\n'
        types = _secret_types(text, [_SECRET], tmp_path)
        assert "FORBIDDEN_TERM" not in types
        assert "aws-access-key" in types

    def test_term_straddling_the_secret_boundary_is_suppressed(self, tmp_path: Path) -> None:
        """Partial intersection counts as overlap."""
        text = f'aws_key = "{_SECRET}"\n'
        types = _secret_types(text, ['"AKIAIOSFO'], tmp_path)
        assert "FORBIDDEN_TERM" not in types


class TestNoRegression:
    def test_separate_lines_still_report_both(self, tmp_path: Path) -> None:
        text = f'aws_key = "{_SECRET}"\n\nThe ProjectOmniInternal rollout begins.\n'
        types = _secret_types(text, ["ProjectOmniInternal"], tmp_path)
        assert "FORBIDDEN_TERM" in types and "aws-access-key" in types

    def test_term_alone_reports(self, tmp_path: Path) -> None:
        types = _secret_types(
            "The ProjectOmniInternal rollout.\n", ["ProjectOmniInternal"], tmp_path
        )
        assert types == ["FORBIDDEN_TERM"]

    def test_credential_alone_reports_no_term(self, tmp_path: Path) -> None:
        types = _secret_types(f'aws_key = "{_SECRET}"\n', ["ProjectOmniInternal"], tmp_path)
        assert "FORBIDDEN_TERM" not in types and "aws-access-key" in types

    def test_clean_line_reports_nothing(self, tmp_path: Path) -> None:
        assert _secret_types("Ordinary prose here.\n", ["ProjectOmniInternal"], tmp_path) == []

    def test_no_forbidden_patterns_configured_is_a_noop(self, tmp_path: Path) -> None:
        types = _secret_types(f'aws_key = "{_SECRET}" ProjectOmniInternal\n', [], tmp_path)
        assert types == ["aws-access-key"]
