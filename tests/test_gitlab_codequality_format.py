# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""`--format gitlab-codequality` must satisfy GitLab's documented schema.

The schema asserted here was read from GitLab's own documentation during
implementation, not recalled: every object needs `description`, `check_name`,
`fingerprint`, `severity` and `location.path` + `location.lines.begin`;
`severity` is one of `info`, `minor`, `major`, `critical`, `blocker`; the path
is relative to the repository root and must not be prefixed with `./`; all line
properties are integers; and the file is a single JSON array with no BOM.

What these tests cannot check is GitLab's *runtime* acceptance — no GitLab
instance is reachable from here. They pin the format against the published
contract, which is the strongest available check; the remaining risk is
recorded rather than papered over.
"""

from __future__ import annotations

import json

import pytest

from zenzic.cli._governance import SuppressionAudit
from zenzic.cli._shared import (
    _GITLAB_SEVERITY,
    _codequality_payload,
)
from zenzic.core.reporter import Finding


def _audit() -> SuppressionAudit:
    """A real SuppressionAudit over its cap: 7 inline + 5 per-file = 12 > 10.

    Deliberately the real frozen dataclass rather than a duck-typed stand-in --
    the payload builder reads .total/.cap/.excess, which are computed
    properties, so a fake that sets them as plain attributes would pass while
    proving nothing about the real type.
    """
    return SuppressionAudit(inline_count=7, per_file_count=5, cap=10)


#: Straight from the documented enum. Anything outside this makes the report
#: unparseable, so the mapping is asserted against the set, not against itself.
GITLAB_SEVERITIES = {"info", "minor", "major", "critical", "blocker"}


def _f(**kw: object) -> Finding:
    base: dict[str, object] = {
        "rel_path": "docs/index.md",
        "line_no": 42,
        "code": "Z101",
        "severity": "warning",
        "message": "Something is wrong.",
    }
    base.update(kw)
    return Finding(**base)  # type: ignore[arg-type]


class TestSchemaConformance:
    def test_payload_is_a_list_of_objects(self) -> None:
        payload = _codequality_payload([_f()])
        assert isinstance(payload, list)
        assert all(isinstance(entry, dict) for entry in payload)

    def test_every_required_field_is_present(self) -> None:
        entry = _codequality_payload([_f()])[0]
        for field in ("description", "check_name", "fingerprint", "severity", "location"):
            assert field in entry, f"GitLab requires {field!r}"
        assert entry["location"]["path"] == "docs/index.md"
        assert entry["location"]["lines"]["begin"] == 42

    def test_line_is_an_integer_not_a_string(self) -> None:
        """GitLab's troubleshooting guide is explicit that line properties are
        integers; JSON-encoding one as a string parses but is rejected."""
        begin = _codequality_payload([_f()])[0]["location"]["lines"]["begin"]
        assert isinstance(begin, int) and not isinstance(begin, bool)

    @pytest.mark.parametrize(
        "zenzic_severity", ["security_breach", "security_incident", "error", "warning", "info"]
    )
    def test_every_zenzic_severity_maps_into_the_documented_enum(
        self, zenzic_severity: str
    ) -> None:
        entry = _codequality_payload([_f(severity=zenzic_severity)])[0]
        assert entry["severity"] in GITLAB_SEVERITIES

    def test_an_unknown_severity_still_maps_into_the_enum(self) -> None:
        """A plugin rule can carry a severity the Core never defined. Emitting it
        verbatim would produce an unparseable report for the whole pipeline, so
        the fallback must be a valid value, not the input."""
        entry = _codequality_payload([_f(severity="totally-made-up")])[0]
        assert entry["severity"] in GITLAB_SEVERITIES

    def test_the_mapping_table_itself_only_contains_legal_values(self) -> None:
        assert set(_GITLAB_SEVERITY.values()) <= GITLAB_SEVERITIES

    def test_severity_is_lowercase(self) -> None:
        """The enum is documented in lowercase and nothing states it is
        case-insensitive, so the safe reading is that it is not."""
        for sev in _GITLAB_SEVERITY.values():
            assert sev == sev.lower()


class TestPathHandling:
    def test_path_is_not_prefixed_with_dot_slash(self) -> None:
        """Called out by name in GitLab's troubleshooting guide as a cause of a
        report that parses but shows nothing."""
        entry = _codequality_payload([_f(rel_path="./docs/index.md")])[0]
        assert entry["location"]["path"] == "docs/index.md"

    def test_windows_separators_are_normalised(self) -> None:
        entry = _codequality_payload([_f(rel_path="docs\\guide\\index.md")])[0]
        assert entry["location"]["path"] == "docs/guide/index.md"

    def test_a_file_level_finding_gets_line_one_not_zero(self) -> None:
        """`line_no == 0` means "the file, not a line" internally. Zero is not a
        line number in any editor and risks rejection, so it clamps to 1 — the
        same choice the SARIF emitter already makes."""
        entry = _codequality_payload([_f(line_no=0)])[0]
        assert entry["location"]["lines"]["begin"] == 1


class TestFingerprint:
    def test_fingerprints_are_unique_across_findings(self) -> None:
        findings = [
            _f(code="Z101", line_no=1),
            _f(code="Z102", line_no=2),
            _f(rel_path="docs/other.md", code="Z101", line_no=1),
        ]
        prints = [e["fingerprint"] for e in _codequality_payload(findings)]
        assert len(set(prints)) == len(prints)

    def test_two_identical_findings_in_one_file_still_get_distinct_fingerprints(self) -> None:
        """The collision case a content hash alone does not cover: the same rule
        firing twice on the same file with the same message. GitLab identifies a
        violation *by* its fingerprint, so a duplicate silently drops one."""
        findings = [_f(line_no=10), _f(line_no=99)]
        prints = [e["fingerprint"] for e in _codequality_payload(findings)]
        assert prints[0] != prints[1]

    def test_fingerprint_is_stable_across_runs(self) -> None:
        """Determinism is Tier-0, and GitLab tracks a violation across commits by
        this value — an unstable one makes every pipeline report everything as
        newly introduced."""
        first = _codequality_payload([_f()])[0]["fingerprint"]
        second = _codequality_payload([_f()])[0]["fingerprint"]
        assert first == second

    def test_fingerprint_does_not_move_when_the_finding_shifts_line(self) -> None:
        """Inserting a paragraph above a finding must not present it as a new
        one. This is why the line number is deliberately not hashed."""
        a = _codequality_payload([_f(line_no=42)])[0]["fingerprint"]
        b = _codequality_payload([_f(line_no=43)])[0]["fingerprint"]
        assert a == b

    def test_fingerprint_does_not_leak_secret_material(self) -> None:
        secret = "AKIAIOSFODNN7EXAMPLE"
        entry = _codequality_payload([_f(code="Z201", match_text=secret)])[0]
        assert secret not in json.dumps(entry)


class TestDeterminismAndOutput:
    def test_output_order_is_deterministic_regardless_of_input_order(self) -> None:
        a = _f(rel_path="b.md", line_no=1, code="Z102")
        b = _f(rel_path="a.md", line_no=9, code="Z101")
        c = _f(rel_path="a.md", line_no=2, code="Z101")
        one = _codequality_payload([a, b, c])
        two = _codequality_payload([c, a, b])
        assert one == two
        paths = [(e["location"]["path"], e["location"]["lines"]["begin"]) for e in one]
        assert paths == sorted(paths)

    def test_empty_findings_produce_an_empty_array_not_null(self) -> None:
        """A clean run must still be a valid report. `null` or an absent file
        makes GitLab show the previous result, or nothing at all."""
        assert _codequality_payload([]) == []

    def test_serialises_to_json_without_a_bom(self) -> None:
        text = json.dumps(_codequality_payload([_f()]))
        assert not text.startswith("﻿")
        assert json.loads(text)[0]["check_name"] == "Z101"

    def test_check_name_is_the_finding_code(self) -> None:
        """GitLab groups and filters by `check_name`, so it has to be the stable
        rule identifier rather than the human message."""
        assert _codequality_payload([_f(code="Z404")])[0]["check_name"] == "Z404"

    def test_description_is_the_human_message(self) -> None:
        entry = _codequality_payload([_f(message="Link target is missing.")])[0]
        assert entry["description"] == "Link target is missing."


class TestSuppressionCapReport:
    """The cap breach aborts the run before findings exist. Every other format
    emits something there; `gitlab-codequality` emitting nothing would hand
    GitLab an empty artifact, which it displays as "no code quality issues" —
    a clean merge request for a failed pipeline."""

    def test_cap_payload_is_a_schema_valid_single_violation(self) -> None:
        from zenzic.cli._governance import build_cap_exceeded_codequality_payload

        audit = _audit()
        payload = build_cap_exceeded_codequality_payload(audit)

        assert isinstance(payload, list) and len(payload) == 1
        entry = payload[0]
        for field in ("description", "check_name", "fingerprint", "severity", "location"):
            assert field in entry
        assert entry["severity"] in GITLAB_SEVERITIES
        assert entry["check_name"] == "SUPPRESSION_CAP_EXCEEDED"
        assert isinstance(entry["location"]["lines"]["begin"], int)
        assert not entry["location"]["path"].startswith("./")

    def test_cap_payload_states_the_numbers_and_the_remedy(self) -> None:
        from zenzic.cli._governance import build_cap_exceeded_codequality_payload

        description = build_cap_exceeded_codequality_payload(_audit())[0]["description"]
        assert "12" in description and "10" in description, "the actual counts must appear"
        assert "emediation" in description or "emedy" in description
