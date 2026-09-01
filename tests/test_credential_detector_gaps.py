# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Input shapes that made a real credential produce exit 0.

Each of these is a *detection* gap, upstream of every suppression guard: the
"never suppressible" contract is enforced on findings, so a finding that is
never constructed is never protected. All four were found by an adversarial
sweep of the detector subsystem and confirmed end-to-end against the CLI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from zenzic.cli._guard import _scan_file_for_secrets
from zenzic.core.credentials import scan_line_for_secrets


_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
_GH = "ghp_" + "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5"


def _types(line: str) -> list[str]:
    return [f.secret_type for f in scan_line_for_secrets(line, Path("x.md"), 1)]


class TestQuickPrefixGateMatchesItsPattern:
    """The github-token regex is ``(?i)`` but its quick-prefix gate listed only
    the all-lower and all-upper spellings, so ``Ghp_``/``gHp_`` satisfied the
    pattern and never reached it — the gate, not the regex, was the real
    decision boundary, and it was narrower than what it guarded."""

    @pytest.mark.parametrize("prefix", ["ghp_", "GHP_", "Ghp_", "gHp_", "GhP_"])
    def test_every_case_spelling_the_pattern_accepts_is_detected(self, prefix: str) -> None:
        body = "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5"
        assert _types(f"token = {prefix}{body}") == ["github-token"], (
            f"the quick-prefix gate rejected {prefix!r}, which its own regex accepts"
        )


class TestBase64GateDoesNotRequirePaddingSymbols:
    """The speculative base64 decode was gated on the line containing ``=``,
    ``+`` or ``/``. A base64 string has no ``=`` when the plaintext length is a
    multiple of 3 and may contain no ``/`` at all — so appending one space to a
    secret before encoding was enough to skip the decode entirely."""

    def test_unpadded_base64_credential_is_detected(self) -> None:
        import base64

        payload = base64.b64encode((_AWS + " ").encode()).decode()
        assert "=" not in payload, "fixture must be unpadded to exercise the gap"
        assert _types(f"key: {payload}"), (
            f"an unpadded base64 credential was skipped by the symbol gate: {payload}"
        )


class TestLongLinesAreNotSilentlyTruncated:
    """``_MAX_LINE_LENGTH`` discarded everything past 1 MiB with no finding and
    no warning. The stated rationale was ReDoS defence, which RE2 makes
    unnecessary — so attacker-controlled padding hid a real secret."""

    def test_secret_past_the_truncation_point_is_still_found(self) -> None:
        line = "A" * (1024 * 1024) + " " + _AWS
        assert _types(line), "a secret past the line-length cutoff was silently dropped"


class TestGuardGateMatchesTheCorpusScan:
    """``guard scan`` scanned line-by-line while the corpus path used the
    cross-line lookback, so a secret split across two lines was caught by
    ``zenzic check`` and missed by the pre-commit gate — the gate being the
    boundary that actually stops the leak entering history."""

    def test_split_token_is_caught_by_the_guard(self, tmp_path: Path) -> None:
        doc = tmp_path / "split.md"
        doc.write_text("k: >-\n  AKIA\n  ABCDEFGHIJKLMNOP\n", encoding="utf-8")
        findings, readable = _scan_file_for_secrets(doc, [])
        assert readable is True
        assert findings, (
            "the pre-commit gate missed a split-token secret that the corpus scan catches"
        )

    def test_non_utf8_file_is_reported_unreadable_not_crashed(self, tmp_path: Path) -> None:
        """``UnicodeDecodeError`` is a ``ValueError``, not an ``OSError``, so it
        escaped the handler, aborted the whole scan, and skipped every later
        file — defeating the fail-closed ``unreadable`` path built for exactly
        this case."""
        doc = tmp_path / "latin1.md"
        doc.write_bytes(b"# Caf\xe9\n\nOrdinary prose.\n")
        findings, readable = _scan_file_for_secrets(doc, [])
        assert findings == []
        assert readable is False, "a non-UTF-8 file must be classed unreadable, not crash"
