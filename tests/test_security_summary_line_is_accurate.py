# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The quiet summary must describe the findings it counted, and the exit it caused.

This is the line a pre-commit user reads to learn what happened and what to do.
It carried two false statements. It called every security-tier finding a
``secret`` to ``rotate`` -- a forbidden scheme is a URL to delete and there is
nothing to rotate -- and it ended in the literal ``Exit 2.`` while the process
exits 3 whenever a system-directory traversal is present.

It also counted by ``severity``, which ``_evaluate_security_exit``'s own
docstring warns against: severity is stamped by whichever subsystem built the
finding and the producers disagree, so a Z203 rendered by ``incremental.py``
carries ``"error"`` and never reached this line at all.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


CONFIG = 'docs_dir = "docs"\nfail_under = 0\n\n[build_context]\nengine = "standalone"\n'
PROSE = (
    "Padding prose so the word-count rule stays quiet and only the security "
    "finding under discussion decides what this page reports today."
)
ZENZIC = shutil.which("zenzic")


def _run(tmp_path: Path, body: str) -> tuple[str, int]:
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".zenzic.toml").write_text(CONFIG, encoding="utf-8")
    (tmp_path / "docs" / "index.md").write_text(f"# T\n\n{body}\n\n{PROSE}\n", encoding="utf-8")
    assert ZENZIC, "the zenzic console script is not on PATH"
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env["COLUMNS"] = "200"
    proc = subprocess.run(  # noqa: S603
        [ZENZIC, "check", "references", "--quiet", "--no-header"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    return proc.stdout + proc.stderr, proc.returncode


CREDENTIAL = 'aws_key = "AKIAIOSFODNN7EXAMPLE"'
SCHEME = "[click me](javascript:alert(1))"
TRAVERSAL = "[t](../../../../../../etc/passwd)"


class TestTheLineNamesWhatItFound:
    def test_a_credential_is_called_a_credential_and_says_to_rotate(self, tmp_path: Path) -> None:
        out, _ = _run(tmp_path, CREDENTIAL)
        assert "credential" in out.lower(), f"a credential was not named as one:\n{out}"
        assert "rotate" in out.lower(), f"the rotation remedy was lost:\n{out}"

    def test_a_forbidden_scheme_is_not_called_a_secret(self, tmp_path: Path) -> None:
        out, _ = _run(tmp_path, SCHEME)
        assert "secret" not in out.lower(), (
            "a forbidden scheme was reported as a secret. It is a URL to delete; "
            f"calling it a secret sends the reader hunting for a credential:\n{out}"
        )

    def test_a_forbidden_scheme_does_not_advise_rotation(self, tmp_path: Path) -> None:
        out, _ = _run(tmp_path, SCHEME)
        assert "rotate" not in out.lower(), (
            f"a forbidden scheme was reported as something to rotate; nothing is:\n{out}"
        )

    def test_a_traversal_reaches_the_line_at_all(self, tmp_path: Path) -> None:
        out, rc = _run(tmp_path, TRAVERSAL)
        assert rc == 3, f"expected the traversal exit, got {rc}:\n{out}"
        assert "SECURITY CRITICAL" in out, (
            "a system-directory traversal produced no security summary at all -- "
            f"it was filtered out by severity rather than by code:\n{out}"
        )


class TestTheStatedExitIsTheRealExit:
    def test_credential_states_the_exit_it_causes(self, tmp_path: Path) -> None:
        out, rc = _run(tmp_path, CREDENTIAL)
        assert rc == 2, f"expected 2, got {rc}"
        assert f"Exit {rc}." in out, f"the line did not state the exit it caused ({rc}):\n{out}"

    def test_scheme_states_the_exit_it_causes(self, tmp_path: Path) -> None:
        out, rc = _run(tmp_path, SCHEME)
        assert rc == 2, f"expected 2, got {rc}"
        assert f"Exit {rc}." in out, f"the line did not state the exit it caused ({rc}):\n{out}"

    def test_traversal_states_three_not_two(self, tmp_path: Path) -> None:
        out, rc = _run(tmp_path, TRAVERSAL)
        assert rc == 3, f"expected 3, got {rc}"
        assert "Exit 3." in out, f"the line claimed the wrong exit code:\n{out}"
        assert "Exit 2." not in out, (
            f"the line hardcoded 'Exit 2.' on a run that exits {rc}:\n{out}"
        )


class TestTheInstrumentIsNotAlwaysFailing:
    """Positive control: a clean document must produce no security line and exit 0."""

    def test_clean_document_is_silent_and_exits_zero(self, tmp_path: Path) -> None:
        out, rc = _run(tmp_path, "[ok](https://example.com)")
        assert rc == 0, f"the clean control did not exit 0, so the rest proves nothing:\n{out}"
        assert "SECURITY CRITICAL" not in out, f"a clean document reported a breach:\n{out}"


class TestTheMappingCannotSilentlyGoIncomplete:
    """A new exit-forcing code must be described, not silently omitted.

    Without this, adding a code to ``SECURITY_BREACH_CODES`` alone would make the
    process exit 2 while the summary line said nothing about why -- the same
    class of divergence as the hardcoded exit code, one level up.
    """

    def test_every_exit_forcing_code_has_a_noun_and_a_remedy(self) -> None:
        from zenzic.core.codes import (
            SECURITY_BREACH_CODES,
            SECURITY_INCIDENT_CODES,
            SECURITY_SUMMARY_TERMS,
        )

        forcing = SECURITY_BREACH_CODES | SECURITY_INCIDENT_CODES
        assert set(SECURITY_SUMMARY_TERMS) == forcing, (
            "SECURITY_SUMMARY_TERMS and the exit-forcing code sets have diverged. "
            f"Missing a description: {sorted(forcing - set(SECURITY_SUMMARY_TERMS))}; "
            f"described but not exit-forcing: {sorted(set(SECURITY_SUMMARY_TERMS) - forcing)}."
        )

    def test_the_exit_authority_agrees_with_the_contract(self) -> None:
        from zenzic.core.codes import security_exit_code

        assert security_exit_code([]) == 0
        assert security_exit_code(["Z101"]) == 0
        assert security_exit_code(["Z201"]) == 2
        assert security_exit_code(["Z204"]) == 2
        assert security_exit_code(["Z205"]) == 2
        assert security_exit_code(["Z203"]) == 3
        assert security_exit_code(["Z201", "Z203"]) == 3, "the incident must dominate the breach"
        assert security_exit_code(["Z202"]) == 0, "Z202 is non-suppressible but exits 1, not 2 or 3"
