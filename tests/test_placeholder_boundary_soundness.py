# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""`is_likely_placeholder` must never be a value the attacker chose.

The flag exists to tell a reviewer "this looks like a documented example". It
is a substring test over the matched span, so it is only sound when the
attacker cannot extend that span. Five of the eight signatures use fixed-length
quantifiers and are safe by construction; three (`github-token`, `slack-token`,
`gitlab-pat`) use open-ended ones, so appending `example` to a live token gets
the suffix swallowed into `match_text` and flips the flag.

The fix is not a tighter alphabet — that was measured and rejected twice over:
it truncated a legitimate 550-character stateless `ghs_` token's match to 13
characters, *and* it still let `example` and `-example` through. Instead the
classifier now refuses to classify a span it cannot trust, returning `False`
("not classifiable") for the unbounded families.

That is a deliberate false negative on a display hint, in the safe direction:
the finding, its severity and its exit code are untouched, because no verdict
path reads this flag.
"""

from __future__ import annotations

import string
from pathlib import Path

import pytest

from zenzic.core.credentials import (
    _SECRETS,
    _is_likely_placeholder,
    scan_line_for_secrets,
)


#: Families whose pattern length is fixed, so the match cannot absorb a suffix.
BOUNDED_FAMILIES = {
    "openai-api-key",
    "aws-access-key",
    "stripe-live-key",
    "google-api-key",
    "private-key",
    "hex-encoded-payload",
}
#: Families with open-ended quantifiers — the attacker controls the tail.
UNBOUNDED_FAMILIES = {"github-token", "slack-token", "gitlab-pat"}

_ALNUM = string.ascii_letters + string.digits

LIVE_TOKENS = {
    "openai-api-key": "sk-" + ("aB3dEfGhIjKlMnOpQrStUvWxYz0123456789AbCdEfGhIjKl"),
    "github-token": "ghp_" + "aB3dEfGhIjKlMnOpQrStUvWxYz0123456789",
    "aws-access-key": "AKIA" + "QRSTUVWX01234567",
    "stripe-live-key": "sk_live_" + "aB3dEfGhIjKlMnOpQrStUvWx",
    "slack-token": "xoxb-" + "aB3dEfGhIjKlMnOpQrStUvWx",
    "google-api-key": "AIza" + "aB3dEfGhIjKlMnOpQrStUvWxYz01234567-_",
    "gitlab-pat": "glpat-" + "aB3dEfGhIjKlMnOpQrStUvWx",
}

#: The canonical true positive: AWS's own published example key. `EXAMPLE` sits
#: at the *end* of the body, which is why no "marker must be at the front" rule
#: could ever have worked.
AWS_PUBLISHED_EXAMPLE = "AKIAIOSFODNN7EXAMPLE"


def _pattern_for(name: str):
    return next(entry[2] for entry in _SECRETS if entry[0] == name)


def _bounded_flag(name: str) -> bool:
    entry = next(e for e in _SECRETS if e[0] == name)
    assert len(entry) == 4, "each signature must declare whether its match is bounded"
    return bool(entry[3])


class TestTheTableDeclaresBoundedness:
    def test_every_signature_declares_a_bounded_flag(self) -> None:
        for entry in _SECRETS:
            assert len(entry) == 4, (
                f"{entry[0]}: no bounded flag — adding a pattern must force this choice"
            )
            assert isinstance(entry[3], bool)

    @pytest.mark.parametrize("name", sorted(BOUNDED_FAMILIES | UNBOUNDED_FAMILIES))
    def test_the_declared_flag_matches_reality(self, name: str) -> None:
        """The flag is a claim about the regex. Verify it against the regex
        rather than trusting the annotation — a wrong flag here silently
        restores the hole or silently disables a working classifier."""
        assert _bounded_flag(name) == (name in BOUNDED_FAMILIES)


class TestUnboundedFamiliesAreNoLongerAppendable:
    @pytest.mark.parametrize("name", sorted(UNBOUNDED_FAMILIES))
    @pytest.mark.parametrize("suffix", [".example", "example", "-example", "XXXXXXXX"])
    def test_appending_a_marker_cannot_flag_a_live_token(self, name: str, suffix: str) -> None:
        token = LIVE_TOKENS[name] + suffix
        match = _pattern_for(name).search(token)
        assert match is not None, "precondition: the token still matches"
        assert _is_likely_placeholder(match.group(0), secret_type=name) is False, (
            f"{name}: an appended {suffix!r} still flips the flag"
        )

    @pytest.mark.parametrize("name", sorted(UNBOUNDED_FAMILIES))
    def test_a_genuine_example_is_also_not_classified(self, name: str) -> None:
        """The accepted cost, asserted rather than left implicit: on these three
        families the classifier now says nothing at all, because it cannot tell
        a documented example from a decorated live token."""
        token = LIVE_TOKENS[name].replace(LIVE_TOKENS[name][-7:], "EXAMPLE")
        assert _is_likely_placeholder(token, secret_type=name) is False


class TestBoundedFamiliesStillWork:
    def test_the_aws_published_example_still_flags(self) -> None:
        """The canonical case this feature exists for. If this regresses, the
        fix has traded the whole feature away rather than repairing it."""
        assert _is_likely_placeholder(AWS_PUBLISHED_EXAMPLE, secret_type="aws-access-key") is True

    def test_the_aws_published_example_flags_end_to_end(self) -> None:
        findings = list(scan_line_for_secrets(f"key = {AWS_PUBLISHED_EXAMPLE}", Path("t.md"), 1))
        assert findings, "precondition: AWS's example key is still detected"
        assert any(f.is_likely_placeholder for f in findings)

    @pytest.mark.parametrize("name", ["openai-api-key", "stripe-live-key", "google-api-key"])
    def test_a_bounded_family_with_a_marker_still_flags(self, name: str) -> None:
        token = LIVE_TOKENS[name]
        marked = token[: -len("EXAMPLE")] + "EXAMPLE"
        assert _pattern_for(name).search(marked) is not None, "precondition: still matches"
        assert _is_likely_placeholder(marked, secret_type=name) is True

    @pytest.mark.parametrize("name", sorted(BOUNDED_FAMILIES & set(LIVE_TOKENS)))
    def test_a_bounded_live_token_is_not_flagged(self, name: str) -> None:
        assert _is_likely_placeholder(LIVE_TOKENS[name], secret_type=name) is False

    def test_repeated_character_run_still_flags_on_a_bounded_family(self) -> None:
        assert _is_likely_placeholder("AKIA" + "X" * 16, secret_type="aws-access-key") is True


class TestForbiddenTermsAreUnaffected:
    """`Z204`'s span is `line[idx : idx + len(term)]` — bounded by the configured
    term, so it was never appendable and must keep classifying."""

    def test_forbidden_term_span_still_classifies(self) -> None:
        assert _is_likely_placeholder("EXAMPLE_TERM", secret_type="FORBIDDEN_TERM") is True


class TestTheFlagStillGatesNoVerdict:
    def test_a_flagged_finding_is_still_reported(self) -> None:
        """Whatever the flag says, the finding is raised. The classifier is a
        display hint and must never become a filter."""
        findings = list(scan_line_for_secrets(f"key = {AWS_PUBLISHED_EXAMPLE}", Path("t.md"), 1))
        assert len(findings) == 1
        assert findings[0].secret_type == "aws-access-key"


class TestUnknownFamilyFailsClosed:
    def test_an_unrecognised_secret_type_is_not_classifiable(self) -> None:
        """A new pattern whose author forgot the flag must lose the cosmetic tag,
        never silently inherit the unsound behaviour."""
        assert _is_likely_placeholder("TOTALLY_EXAMPLE", secret_type="brand-new-type") is False
