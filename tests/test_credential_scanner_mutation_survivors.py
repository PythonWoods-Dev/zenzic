# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Field- and branch-level assertions closing real mutation-survivor gaps.

``src/zenzic/core/credentials.py`` is scoped for mutation testing
(``pyproject.toml``'s ``[tool.mutmut]``) because it is the Z201/Z204 detection
path. A full survivor triage (``V031_MUTATION_SURVIVOR_TRIAGE_AND_KILL``) found
that most of the surviving mutants were not missing edge cases so much as
missing *assertions*: existing tests exercise the happy path but only check
``secret_type``/finding count, never the other ``SecurityFinding`` fields
(``file_path``, ``line_no``, ``url``, ``col_start``, ``match_text``,
``is_likely_placeholder``) or the specific branch (fast RE2-union path vs. the
linear fallback; raw-line vs. normalised-only match; base64-decoded rescan;
cross-line lookback) that produced the finding.

Each test below targets a specific branch or field identified by that triage,
not a hypothetical gap — see the triage's own report for which mutant IDs each
test kills.
"""

from __future__ import annotations

import base64
from pathlib import Path

from zenzic.core.credentials import (
    CredentialViolation,
    SecurityFinding,
    _gate_open,
    _is_likely_placeholder,
    _normalize_line_for_scan,
    _try_decode_base64,
    safe_read_line,
    scan_line_for_forbidden_terms,
    scan_line_for_secrets,
    scan_lines_with_lookback,
    scan_security_findings,
    scan_url_for_secrets,
)
from zenzic.models.config import ZenzicConfig


_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"


# ── _gate_open: the quick-reject prefilter ─────────────────────────────────


class TestGateOpenRejectsCleanText:
    """``_gate_open`` must return ``None`` (skip the whole signature table) for
    text containing none of the known secret-prefix substrings — that is the
    entire point of the pre-filter."""

    def test_plain_prose_is_rejected(self) -> None:
        assert _gate_open("Ordinary prose with no secret markers at all.") is None

    def test_text_with_a_known_prefix_is_not_rejected(self) -> None:
        assert _gate_open(f"key: {_AWS}") is not None


# ── _try_decode_base64: validate= and errors= must matter ──────────────────


class TestTryDecodeBase64ValidationAndErrorHandling:
    """``validate=True`` must actually reject non-alphabet characters (rather
    than silently stripping them), and ``errors="ignore"`` must actually
    recover a secret sitting next to an invalid UTF-8 byte."""

    def test_invalid_characters_are_rejected_not_silently_stripped(self) -> None:
        # '!' is not in the base64 alphabet. With validate=True this must
        # raise (caught internally) and return None -- not silently decode
        # whatever remains after stripping the invalid character.
        assert _try_decode_base64("YWJj!ZGVm") is None

    def test_invalid_utf8_byte_does_not_hide_the_rest_of_the_decode(self) -> None:
        # A leading invalid-UTF-8 byte followed by genuine ASCII secret text.
        # errors="ignore" must drop the bad byte and keep decoding; errors
        # defaulting to "strict" would raise UnicodeDecodeError (caught as a
        # ValueError) and return None, losing the recoverable secret text.
        raw = b"\xff" + _AWS.encode("ascii")
        token = base64.b64encode(raw).decode()
        decoded = _try_decode_base64(token)
        assert decoded is not None
        assert _AWS in decoded


# NOTE: two mutants to the final `.decode(...)` call are not tested. Dropping
# the explicit "utf-8" positional argument is equivalent because "utf-8" is
# already `bytes.decode`'s own default in CPython; changing it to "UTF-8" is
# equivalent because Python's codec registry normalises encoding names
# case-insensitively -- neither mutation is observable through any decode
# result, real or contrived.


# ── _is_likely_placeholder: the exact 8-character run boundary ────────────


class TestPlaceholderRunLengthBoundary:
    """The docstring's own claim is "a run of 8+ identical characters" --
    pinned here at the exact boundary, not just at run lengths far past it."""

    def test_run_of_seven_is_not_a_placeholder(self) -> None:
        # A preceding different character exercises the run-restart logic too
        # (each new run must start counting from 1, not from a value already
        # close to the 8 threshold).
        assert _is_likely_placeholder("X" + "A" * 7) is False

    def test_run_of_exactly_eight_is_a_placeholder(self) -> None:
        assert _is_likely_placeholder("A" * 8) is True


# NOTE: four mutants to `run_char`'s and `run_len`'s *initial* values
# (`run_char = ""` -> `None`/`"XXXX"`; `run_len = 0` -> `None`/`1`) are not
# tested. `run_char` starts as a sentinel compared against a single iterated
# character on the very first loop pass; no single character is ever `==` to
# `""`, `None`, or a 4-character string, so that comparison is always False
# regardless of the mutation, and the `else` branch immediately overwrites
# both `run_char` and `run_len` before either is read again. Both initial
# values are therefore unreachable, not merely untested.


# ── _normalize_line_for_scan: the fast-path shortcut's own exact boundary ──


class TestNormalizeLineForScanFastPathBoundary:
    """The fast path returns the line untouched (just whitespace-collapsed)
    only when *none* of the seven noise markers are present. A line carrying
    all seven at once must still go through full normalisation, not take the
    untouched shortcut."""

    def test_line_with_all_markers_is_fully_normalized(self) -> None:
        line = "`AKIA` + `ABCDEFGHIJKLMNOP` | note & <!-- c --> {/* c */} \r"
        result = _normalize_line_for_scan(line)
        # The raw line's noise (backticks, concat operator, table pipe) must
        # be gone -- the fast-path shortcut would return it untouched instead.
        assert "`" not in result
        assert _AWS in result

    def test_lone_plus_sign_is_still_stripped(self) -> None:
        # No backticks here -- with them present the fast path is already
        # disqualified by the (unmutated) backtick check, which would mask
        # a mutation to the "+" tuple entry specifically. This line's only
        # marker is the lone "+".
        line = "AKIA + ABCDEFGHIJKLMNOP"
        assert _normalize_line_for_scan(line) == _AWS

    # NOTE: a lone "\r" (no other marker) is not tested here. `.split()` in
    # both the fast path and the slow path's own final collapse step treats
    # \r as whitespace and discards it identically either way, so the two
    # paths converge on the same output regardless of which one a mutation
    # to the "\r" tuple entry routes execution through -- equivalent given
    # this module's actual normalisation behaviour, not chased further. See
    # the mutation-survivor triage report for the full reasoning.


# ── scan_line_for_forbidden_terms: fast path vs. fallback, and every field ─


class TestForbiddenTermsFastPathFields:
    """The RE2 pre-compiled union path (used whenever a config supplies
    ``forbidden_patterns_compiled``) yields a finding whose fields were never
    individually asserted -- only whether *a* finding appeared."""

    def test_fields_are_correct_on_a_fast_path_match(self) -> None:
        config = ZenzicConfig(docs_dir=Path("docs"), forbidden_patterns=["SecretProjectName"])
        line = "codename: SecretProjectName rollout\n"
        findings = list(
            scan_line_for_forbidden_terms(
                line,
                config.forbidden_patterns,
                Path("x.md"),
                7,
                compiled_pattern=config.forbidden_patterns_compiled,
            )
        )
        assert len(findings) == 1
        f = findings[0]
        assert f.file_path == Path("x.md")
        assert f.line_no == 7
        assert f.secret_type == "FORBIDDEN_TERM"
        assert f.url == line.strip()
        assert f.col_start == line.index("SecretProjectName")
        assert f.match_text == "SecretProjectName"
        assert f.is_likely_placeholder is False

    def test_placeholder_classified_term_is_flagged_on_the_fast_path(self) -> None:
        config = ZenzicConfig(
            docs_dir=Path("docs"), forbidden_patterns=["SecretProjectNameEXAMPLE"]
        )
        findings = list(
            scan_line_for_forbidden_terms(
                "codename: SecretProjectNameEXAMPLE\n",
                config.forbidden_patterns,
                Path("x.md"),
                1,
                compiled_pattern=config.forbidden_patterns_compiled,
            )
        )
        assert findings[0].is_likely_placeholder is True

    def test_fast_path_is_actually_used_when_compiled_pattern_is_given(self) -> None:
        """A forbidden_patterns list that would NOT match the line, paired
        with a compiled_pattern that WOULD, distinguishes the fast path from
        the fallback: only the fast path can find this match."""
        config = ZenzicConfig(docs_dir=Path("docs"), forbidden_patterns=["SecretProjectName"])
        findings = list(
            scan_line_for_forbidden_terms(
                "codename: SecretProjectName rollout\n",
                ["some-other-term-not-in-this-line"],
                Path("x.md"),
                1,
                compiled_pattern=config.forbidden_patterns_compiled,
            )
        )
        assert len(findings) == 1, (
            "compiled_pattern must drive the match, not the (mismatched) forbidden_patterns list"
        )


class TestForbiddenTermsFallbackPathFields:
    """The linear fallback (no compiled_pattern -- the exact call shape
    ``zenzic guard scan`` uses, the pre-commit hook's own detection path) had
    zero coverage anywhere in the test suite before this: ``coverage.json``
    showed every line of it unexecuted project-wide."""

    def test_fields_are_correct_on_a_fallback_match(self) -> None:
        line = "codename: SecretProjectName rollout\n"
        findings = list(scan_line_for_forbidden_terms(line, ["SecretProjectName"], Path("x.md"), 3))
        assert len(findings) == 1
        f = findings[0]
        assert f.file_path == Path("x.md")
        assert f.line_no == 3
        assert f.secret_type == "FORBIDDEN_TERM"
        assert f.url == line.strip()
        assert f.col_start == line.index("SecretProjectName")
        assert f.match_text == "SecretProjectName"
        assert f.is_likely_placeholder is False

    def test_placeholder_classified_term_is_flagged_on_the_fallback(self) -> None:
        findings = list(
            scan_line_for_forbidden_terms(
                "codename: SecretProjectNameEXAMPLE\n",
                ["SecretProjectNameEXAMPLE"],
                Path("x.md"),
                1,
            )
        )
        assert findings[0].is_likely_placeholder is True

    def test_first_occurrence_wins_not_the_last(self) -> None:
        """``.find()`` (first occurrence), not ``.rfind()`` (last) -- a term
        repeated on the same line must report the first, not the last,
        position."""
        line = "SecretProjectName ... SecretProjectName again\n"
        findings = list(scan_line_for_forbidden_terms(line, ["SecretProjectName"], Path("x.md"), 1))
        assert findings[0].col_start == line.index("SecretProjectName")

    def test_matching_is_case_insensitive(self) -> None:
        findings = list(
            scan_line_for_forbidden_terms(
                "CODENAME: secretprojectname\n", ["SecretProjectName"], Path("x.md"), 1
            )
        )
        assert len(findings) == 1

    def test_no_match_yields_nothing(self) -> None:
        findings = list(
            scan_line_for_forbidden_terms(
                "nothing forbidden here\n", ["SecretProjectName"], Path("x.md"), 1
            )
        )
        assert findings == []

    def test_first_match_wins_one_finding_per_line(self) -> None:
        findings = list(
            scan_line_for_forbidden_terms(
                "SecretProjectName and OtherForbiddenTerm\n",
                ["SecretProjectName", "OtherForbiddenTerm"],
                Path("x.md"),
                1,
            )
        )
        assert len(findings) == 1


# ── scan_url_for_secrets: every field, and the str-file_path conversion ───


class TestScanUrlForSecretsFields:
    def test_fields_are_correct_and_string_file_path_is_converted(self) -> None:
        url = f"https://example.com/creds/{_AWS}"
        findings = list(scan_url_for_secrets(url, "docs/page.md", 5))
        assert len(findings) == 1
        f = findings[0]
        assert isinstance(f.file_path, Path)
        assert f.file_path == Path("docs/page.md")
        assert f.line_no == 5
        assert f.secret_type == "aws-access-key"
        assert f.url == url
        assert f.col_start == url.index(_AWS)
        assert f.match_text == _AWS
        assert f.is_likely_placeholder is False


# ── scan_line_for_secrets: normalized-only col_start, and base64 rescan ───


class TestScanLineForSecretsNormalizedOnlyColStart:
    """When a secret is only reconstructed via normalisation (the module's own
    documented split-token example), ``col_start`` must fall back to 0 rather
    than reporting a raw-line search position that does not exist."""

    def test_split_token_via_table_pipes_reports_col_start_zero(self) -> None:
        line = "| Key ID | `AKIA` + `ABCDEFGHIJKLMNOP` |\n"
        findings = list(scan_line_for_secrets(line, Path("x.md"), 1))
        aws = [f for f in findings if f.secret_type == "aws-access-key"]
        assert aws, "the documented split-token example must still be detected"
        assert aws[0].col_start == 0


class TestScanLineForSecretsAlreadySeenDoesNotAbortTheScan:
    """Skipping an already-seen secret type must move on to the next entry in
    the signature table (``continue``), not abort the whole table
    (``break``) -- otherwise a second, genuinely different secret type later
    in the table, found only via the normalised form, is silently dropped."""

    def test_a_second_distinct_secret_found_only_via_normalisation_is_not_dropped(
        self,
    ) -> None:
        # The openai key matches in the raw form (added to `seen` first,
        # since it is earlier in `_SECRETS_GATE`); the github token is only
        # reconstructable after backtick/concat-operator normalisation, and
        # comes later in the table -- exactly the ordering `break` would corrupt.
        openai = "sk-" + "A" * 48
        gh_body = "a" * 36
        line = f"{openai} `ghp_` + `{gh_body}`\n"
        types = {f.secret_type for f in scan_line_for_secrets(line, Path("x.md"), 1)}
        assert types == {"openai-api-key", "github-token"}


class TestScanLineForSecretsRawFormFields:
    """The raw/normalised dual-form loop's own yield had unasserted fields."""

    def test_string_file_path_is_converted_and_url_is_the_raw_line(self) -> None:
        line = f"prefix {_AWS} suffix\n"
        findings = list(scan_line_for_secrets(line, "docs/page.md", 1))
        aws = [f for f in findings if f.secret_type == "aws-access-key"][0]
        assert isinstance(aws.file_path, Path)
        assert aws.file_path == Path("docs/page.md")
        assert aws.url == line.strip()


class TestScanLineForSecretsBase64RescanFields:
    """The base64 speculative-decode success path (``_decoded is None: continue``
    never taken) had zero coverage project-wide -- ``coverage.json`` line 429
    was unexecuted by the entire suite, not just mutmut's scope."""

    def test_base64_hidden_secret_fields_are_correct(self) -> None:
        # AWS's own published example key -- also trips the placeholder
        # classifier, distinguishing a correctly-set is_likely_placeholder
        # from one that silently defaulted to False.
        example_key = "AKIA" + "IOSFODNN7EXAMPLE"
        payload = base64.b64encode(example_key.encode()).decode()
        line = f"blob: {payload}\n"
        findings = list(scan_line_for_secrets(line, Path("x.md"), 9))
        b64 = [f for f in findings if f.secret_type == "aws-access-key"]
        assert b64, "a base64-encoded secret must be recovered by the speculative decoder"
        f = b64[0]
        assert f.file_path == Path("x.md")
        assert f.line_no == 9
        assert f.url == line.strip()
        assert f.col_start == 0
        assert f.match_text == example_key
        assert f.is_likely_placeholder is True

    def test_candidate_shorter_than_twenty_chars_is_not_decoded(self) -> None:
        # A short base64-looking token must never reach the decoder at all --
        # asserting on absence, not just on the short-candidate not matching.
        short_payload = base64.b64encode(b"AKIA123").decode()
        assert len(short_payload) < 20
        findings = list(scan_line_for_secrets(f"x: {short_payload}\n", Path("x.md"), 1))
        assert findings == []

    def test_normalized_length_boundary_at_exactly_twenty(self) -> None:
        """The 20-char *normalised-line* length floor: a normalised line of
        exactly 20 characters must still be scanned (``>= 20``, not ``> 20``
        or ``>= 21``)."""
        payload = base64.b64encode(b"\\x41\\x42\\x43xyz").decode()  # 15 bytes -> 20 chars
        assert len(payload) == 20
        findings = list(scan_line_for_secrets(f"{payload}\n", Path("x.md"), 1))
        assert any(f.secret_type == "hex-encoded-payload" for f in findings)

    def test_candidate_length_boundary_at_exactly_twenty(self) -> None:
        """The 20-char *candidate* length floor: a candidate of exactly 20
        characters (bounded by non-base64-alphabet separators either side)
        must still be decoded (``< 20`` skips shorter, not ``<= 20``/``< 21``)."""
        payload = base64.b64encode(b"\\x41\\x42\\x43xyz").decode()
        assert len(payload) == 20
        line = f"prefix: {payload} suffix\n"
        findings = list(scan_line_for_secrets(line, Path("x.md"), 1))
        assert any(f.secret_type == "hex-encoded-payload" for f in findings)

    def test_a_short_or_undecodable_or_gateless_candidate_does_not_abort_the_scan(
        self,
    ) -> None:
        """Three consecutive guards (too short; fails to decode; decodes but
        matches no known prefix) must each ``continue`` to the next candidate
        in the line, not ``break`` out of scanning the line entirely."""
        too_short = base64.b64encode(b"abcdefgh").decode()  # matches the regex, < 20 chars
        undecodable = base64.b64encode(b"\x80" * 15).decode()  # decodes to "" -> None
        no_prefix = base64.b64encode(b"totally boring1").decode()  # decodes, no known prefix
        valid = base64.b64encode(b"\\x41\\x42\\x43xyz").decode()  # decodes, real secret
        line = f"{too_short} {undecodable} {no_prefix} {valid}\n"
        findings = list(scan_line_for_secrets(line, Path("x.md"), 1))
        assert any(f.secret_type == "hex-encoded-payload" for f in findings), (
            "a valid candidate after a short/undecodable/gateless one must still be found"
        )

    def test_already_seen_type_does_not_abort_the_base64_rescan(self) -> None:
        """Same already-seen ``continue``-not-``break`` requirement as the
        raw/normalised loop, but for the base64 rescan's own signature loop."""
        openai = "sk-" + "A" * 48  # earlier in _SECRETS_GATE, found via raw text
        hex_payload = base64.b64encode(b"\\x41\\x42\\x43xyz").decode()  # later, base64-only
        line = f"{openai} blob: {hex_payload}\n"
        types = {f.secret_type for f in scan_line_for_secrets(line, Path("x.md"), 1)}
        assert types == {"openai-api-key", "hex-encoded-payload"}

    def test_string_file_path_is_converted_through_the_base64_rescan(self) -> None:
        payload = base64.b64encode(_AWS.encode()).decode()
        findings = list(scan_line_for_secrets(f"blob: {payload}\n", "docs/page.md", 1))
        b64 = [f for f in findings if f.secret_type == "aws-access-key"][0]
        assert isinstance(b64.file_path, Path)
        assert b64.file_path == Path("docs/page.md")

    def test_dedup_within_the_base64_rescan_uses_the_real_secret_type(self) -> None:
        """The base64 loop's own ``seen.add(secret_type)`` must record the
        real type -- otherwise a second, different base64 candidate decoding
        to another instance of the *same* secret type is not recognised as
        a duplicate and gets reported twice."""
        key_a = "AKIA" + "ABCDEFGHIJKLMNOP"
        key_b = "AKIA" + "QRSTUVWXYZABCDEF"
        line = (
            f"blob1: {base64.b64encode(key_a.encode()).decode()} "
            f"blob2: {base64.b64encode(key_b.encode()).decode()}\n"
        )
        aws = [
            f
            for f in scan_line_for_secrets(line, Path("x.md"), 1)
            if f.secret_type == "aws-access-key"
        ]
        assert len(aws) == 1, f"expected exactly one deduplicated finding, got {len(aws)}"


# NOTE: removing the base64 rescan's `col_start=0` kwarg is not tested. Unlike
# every other field in this yield, the correct value here is not computed --
# it is a hardcoded `0` ("position in decoded text is meaningless in raw
# line"), which is also `SecurityFinding.col_start`'s own dataclass default.
# Removing the kwarg falls back to the exact same value the code always
# assigns, so no observation can ever tell the two apart.


# ── scan_lines_with_lookback: the cross-line match's own fields ───────────


class TestScanLinesWithLookbackCrossLineFields:
    """The ZRT-007 cross-line join's own successful match (the module
    docstring's own YAML-folded-scalar example) had zero field-level
    assertions anywhere in the suite."""

    def test_cross_line_split_secret_fields_are_correct(self) -> None:
        # AWS's own published example key -- the module docstring's own
        # example -- also trips the placeholder classifier, distinguishing a
        # correctly-computed is_likely_placeholder from one that silently
        # defaulted to False.
        lines = [(1, "api_key: >-\n"), (2, "  AKIA\n"), (3, "  IOSFODNN7EXAMPLE\n")]
        findings = list(scan_lines_with_lookback(iter(lines), Path("x.md")))
        cross_line = [f for f in findings if f.secret_type == "aws-access-key"]
        assert cross_line, "a secret split across two lines must be reconstructed"
        f = cross_line[0]
        assert f.file_path == Path("x.md")
        assert f.match_text == "AKIAIOSFODNN7EXAMPLE"
        assert f.col_start == 0
        assert f.is_likely_placeholder is True
        assert f.url == "IOSFODNN7EXAMPLE"
        # line_no is whichever of the two joined lines the join logic attributes
        # the match to -- assert it is one of the two real lines, not an
        # untested/corrupted value.
        assert f.line_no in (2, 3)

    def test_first_line_of_a_file_never_spuriously_joins(self) -> None:
        """There is no previous line on line 1 -- the lookback join must not
        run at all, regardless of what the (falsy) initial buffer looks like."""
        lines = [(1, f"{_AWS}\n")]
        findings = list(scan_lines_with_lookback(iter(lines), Path("x.md")))
        # Exactly one finding (from the per-line scan) -- not a second,
        # spurious one from an incorrectly-truthy initial lookback buffer.
        assert len([f for f in findings if f.secret_type == "aws-access-key"]) == 1


# NOTE: `prev_normalized`'s and `prev_seen`'s *initial* values (`""` -> `None`;
# `set()` -> `None`) are not tested. Both are only ever read inside `if
# prev_normalized:`, which is False for both the real value and `None` on the
# very first loop iteration (an empty string and `None` are both falsy), and
# both are unconditionally overwritten at the end of every iteration before a
# second read could occur -- unreachable, not merely untested. `prev_normalized
# = "XXXX"` (truthy, unlike `""`) is also not tested: it would make the very
# first line spuriously attempt a lookback join, but "XXXX" cannot form a
# prefix of any signature in `_SECRETS`, and any of the current line's own
# content the join could otherwise expose is already found by that line's own
# per-line scan -- no real input can make this mutation observable.


class TestScanLinesWithLookbackAlreadySeenAndDedup:
    def test_already_seen_type_does_not_abort_the_join_scan(self) -> None:
        """Same already-seen ``continue``-not-``break`` requirement as the
        per-line scanner, but for the lookback join's own signature loop:
        line 1 alone contains a complete AWS key (added to ``prev_seen``,
        earlier in ``_SECRETS_GATE``); the join of line 1's tail with line 2's
        head reconstructs a *different*, later-in-table secret (slack-token)
        that only the join can see."""
        lines = [(1, f"prefix {_AWS} xox\n"), (2, "b-1234567890123\n")]
        findings = list(scan_lines_with_lookback(iter(lines), Path("x.md")))
        types = {f.secret_type for f in findings}
        assert types == {"aws-access-key", "slack-token"}

    def test_dedup_buffer_is_keyed_by_the_real_secret_type(self) -> None:
        """The join's own dedup set must record the *real* secret_type it
        found, not a corrupted placeholder value -- otherwise the same
        secret type reconstructed again from the next line's join is not
        recognised as already reported, producing a duplicate finding for
        what the ``already_seen`` mechanism exists to suppress."""
        lines = [
            (1, "prefix1 AKIA\n"),
            (2, "ABCDEFGHIJKLMNOP suffix AKIA\n"),
            (3, "QRSTUVWXYZABCDEF\n"),
        ]
        findings = list(scan_lines_with_lookback(iter(lines), Path("x.md")))
        aws = [f for f in findings if f.secret_type == "aws-access-key"]
        assert len(aws) == 1, (
            f"expected exactly one deduplicated aws-access-key finding, got {len(aws)}"
        )


# NOTE: the 80-vs-81-character lookback window boundary (mutants targeting
# `prev_normalized[-80:]` and `current_normalized[:80]`) is not tested here.
# Both slices are anchored at the end the needed content is anchored to (the
# previous line's tail, the current line's head), so any padding a window
# truncates is necessarily padding that plays no part in a real match --
# truncating it can never change whether a match occurs. Every fixed-length
# signature in `_SECRETS` is well under 80 characters, and the one
# open-ended pattern (`hex-encoded-payload`, `{3,}`) degrades to a shorter
# still-valid match under truncation rather than failing outright. See the
# mutation-survivor triage report for the full reasoning -- documented as
# equivalent-in-practice rather than chased with a contrived construction.
#
# The join's own yield also hardcodes `col_start=0` (the joined text's
# position is meaningless in either raw line), which is `SecurityFinding
# .col_start`'s own dataclass default -- removing that kwarg is equivalent to
# setting it, for the same reason as the base64 rescan's identical case above.


# ── CredentialViolation and safe_read_line ─────────────────────────────────


# ── scan_security_findings: the credential/forbidden-term interaction ─────


class TestScanSecurityFindingsRawLineIndexing:
    """``lines[finding.line_no - 1]`` must fetch the *correct* raw line -- an
    off-by-one here silently misclassifies a perfectly well-positioned
    credential as opaque, which then wrongly suppresses an unrelated
    forbidden term sharing its line."""

    def test_correct_line_is_fetched_not_an_off_by_one_neighbor(self) -> None:
        # A second, differently-worded line is required: if the fetch is
        # off by one and wraps to some *other* line's content, that content
        # must be visibly different for the mismatch to manifest.
        text = f'aws_key = "{_AWS}"  # ProjectXInternal note\nunrelated second line for padding\n'
        config = ZenzicConfig(docs_dir=Path("docs"), forbidden_patterns=["ProjectXInternal"])
        types = {f.secret_type for f in scan_security_findings(text, Path("x.md"), config)}
        assert types == {"aws-access-key", "FORBIDDEN_TERM"}, (
            "a credential on a correctly-classified (non-opaque) line must not "
            "suppress an unrelated forbidden term sharing that same line"
        )


class TestScanSecurityFindingsOpaqueLineTracking:
    def test_opaque_line_is_recorded_by_its_real_line_number(self) -> None:
        """A credential whose position is genuinely unknown (reconstructed by
        the cross-line lookback) must suppress a forbidden term embedded
        *within* it -- the whole point of the opaque-line fallback -- keyed
        by the finding's real line number, not a corrupted one."""
        text = "api_key: >-\n  AKIA\n  IOSFODNN7EXAMPLE ProjectYInternal\n"
        config = ZenzicConfig(docs_dir=Path("docs"), forbidden_patterns=["ProjectYInternal"])
        findings = scan_security_findings(text, Path("x.md"), config)
        assert [f.secret_type for f in findings] == ["aws-access-key"], (
            "a forbidden term embedded in an opaque (position-unknown) credential "
            "line must stay suppressed -- it must not gain a second panel"
        )

    def test_an_early_opaque_line_does_not_abort_scanning_later_lines(self) -> None:
        """The opaque-line skip must ``continue`` to the next line, not
        ``break`` out of the whole forbidden-term pass."""
        text = "api_key: >-\n  AKIA\n  IOSFODNN7EXAMPLE\nline4\nProjectZInternal here\n"
        config = ZenzicConfig(docs_dir=Path("docs"), forbidden_patterns=["ProjectZInternal"])
        types = {f.secret_type for f in scan_security_findings(text, Path("x.md"), config)}
        assert types == {"aws-access-key", "FORBIDDEN_TERM"}, (
            "a clean forbidden term several lines after an opaque credential must still be found"
        )


class TestScanSecurityFindingsUsesTheRealCompiledPattern:
    """The forbidden-term pass must actually use the config's compiled RE2
    union pattern, not silently fall back to the linear scan -- the two
    differ in match order when the pattern list isn't already sorted by
    where its terms occur in the text: the fast path reports the leftmost
    match in the *string*; the fallback reports the first match in *list*
    order, regardless of position."""

    def test_leftmost_match_wins_not_first_in_the_pattern_list(self) -> None:
        # "Zebra" is listed first but occurs second in the text; the fast
        # (compiled) path must report "Apple" (leftmost), not "Zebra".
        text = "Apple and Zebra rollout\n"
        config = ZenzicConfig(docs_dir=Path("docs"), forbidden_patterns=["Zebra", "Apple"])
        findings = scan_security_findings(text, Path("x.md"), config)
        assert len(findings) == 1
        assert findings[0].match_text == "Apple"


class TestScanSecurityFindingsAdjacencyIsNotOverlap:
    """The half-open interval check's own exact boundary -- zero-gap
    adjacency, not the one-character-gap "adjacent" case a quote character
    already covered elsewhere. A term that starts exactly where a credential
    ends (or ends exactly where one starts) touches it but does not overlap
    it, and must still be reported."""

    _SECRET = "AKIAIOSFODNN7EXAMPLE"

    def test_term_starting_exactly_at_the_secret_s_end_is_reported(self) -> None:
        text = f"{self._SECRET}ProjectOmniInternal\n"
        config = ZenzicConfig(docs_dir=Path("docs"), forbidden_patterns=["ProjectOmniInternal"])
        types = {f.secret_type for f in scan_security_findings(text, Path("x.md"), config)}
        assert types == {"aws-access-key", "FORBIDDEN_TERM"}

    def test_term_ending_exactly_at_the_secret_s_start_is_reported(self) -> None:
        text = f"ProjectOmniInternal{self._SECRET}\n"
        config = ZenzicConfig(docs_dir=Path("docs"), forbidden_patterns=["ProjectOmniInternal"])
        types = {f.secret_type for f in scan_security_findings(text, Path("x.md"), config)}
        assert types == {"aws-access-key", "FORBIDDEN_TERM"}


# NOTE: `text.splitlines(keepends=True)` vs `keepends=None`/`False` is not
# tested here. Every downstream consumer either regex-matches content that
# never spans into a line terminator, or applies `.strip()`/`.split()`-based
# whitespace normalisation that erases the terminator's presence before it
# reaches any assertion surface -- equivalent in practice for this module's
# actual usage, not chased with a contrived construction. Nor is the
# `else ""` vs `else "XXXX"` out-of-bounds fallback in the raw_line fetch:
# `finding.line_no` is always produced by the same `enumerate(lines,
# start=1)` this function itself constructs, so it can never exceed
# `len(lines)` through this function's own call path -- the guarded branch
# is unreachable defensive code, not a live gap. `continue` vs `break` on
# the forbidden-term overlap check (mutant 66) is also not tested:
# `scan_line_for_forbidden_terms` yields at most one finding per line
# (first-match-wins, with an explicit early `return`), so that loop body
# runs at most once and `continue`/`break` are behaviourally identical.
# See the mutation-survivor triage report for the full reasoning on all three.


class TestCredentialViolationCarriesTheRealFinding:
    def test_finding_attribute_and_message_are_correct(self) -> None:
        finding = SecurityFinding(
            file_path=Path("x.md"),
            line_no=4,
            secret_type="aws-access-key",
            url=_AWS,
            col_start=0,
            match_text=_AWS,
            is_likely_placeholder=False,
        )
        exc = CredentialViolation(finding)
        assert exc.finding is finding
        assert "aws-access-key" in str(exc)
        assert "x.md" in str(exc)
        assert "4" in str(exc)


class TestSafeReadLinePassesTheRealLineNumber:
    def test_violation_reports_the_real_line_no(self) -> None:
        try:
            safe_read_line(f"key: {_AWS}\n", Path("x.md"), 42)
        except CredentialViolation as exc:
            assert exc.finding.line_no == 42
        else:
            raise AssertionError("expected a CredentialViolation to be raised")
