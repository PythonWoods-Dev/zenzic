# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The security tier's exit code has one authority, keyed on code not severity.

Three separate defects were each one branch returning ahead of the exit-code
contract: the ``Z906`` "audit skipped" shortcut, ``guard scan``'s clean bill
over an unreadable file, and the corrupt-baseline handler below. Patching them
individually would not have stopped the fourth, because the underlying cause is
that *"is this a security finding"* had two authorities — the finding's **code**
(structural, used by SARIF) and its **severity** (set by whichever subsystem
constructed it, and producers disagree).

``incremental.py`` emits ``Z203`` with ``code_severity("Z203") == "error"``,
so a severity-keyed test reported a rendered path traversal as an ordinary
quality finding. That is how ``check references`` came to exit 1 on a Z203
while its own SARIF output for the same run said "Critical security finding
detected: Z203".
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from zenzic.core.codes import (
    SECURITY_BREACH_CODES,
    SECURITY_INCIDENT_CODES,
    SECURITY_TIER_CODES,
)
from zenzic.main import app


_SECRET = "AKIA" + "IOSFODNN7EXAMPLE"
_PROSE = (
    "This page carries a comfortable amount of prose so the minimum word-count "
    "check stays quiet and only the finding under discussion is reported here."
)


def _project(tmp_path: Path, body: str) -> None:
    (tmp_path / "mkdocs.yml").write_text("site_name: Demo\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n', encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text(f"# Page\n\n{_PROSE}\n\n{body}\n", encoding="utf-8")


def _run(tmp_path: Path, *args: str) -> int:
    return (
        CliRunner()
        .invoke(
            app, ["check", *args, str(tmp_path / "docs"), "--no-header"], catch_exceptions=False
        )
        .exit_code
    )


class TestTheTierIsFullyClassified:
    def test_every_tier_code_has_a_decided_exit(self) -> None:
        """A new tier member must not be able to ship with undecided semantics.

        ``Z202`` is deliberately in neither subset: it is non-suppressible but
        reports at the ordinary error tier, per the Exit Code Contract, which
        names only ``Z203`` for exit 3 and ``Z201``/``Z204``/``Z205`` for exit 2.
        """
        undecided = SECURITY_TIER_CODES - SECURITY_INCIDENT_CODES - SECURITY_BREACH_CODES
        assert undecided == {"Z202"}, (
            f"security-tier codes with no decided exit code: {sorted(undecided)} — "
            "classify each into SECURITY_INCIDENT_CODES or SECURITY_BREACH_CODES"
        )

    def test_the_two_subsets_do_not_overlap(self) -> None:
        assert not (SECURITY_INCIDENT_CODES & SECURITY_BREACH_CODES)


class TestCorruptBaselineCannotDowngradeABreach:
    """B-1: the baseline handler raised ``typer.Exit(1)`` upstream of the exit
    evaluation, and ``all_findings`` is populated well before it. Since
    ``.zenzic-baseline.json`` is a checked-in, writable artifact, a one-byte
    corruption downgraded a live credential from exit 2 to exit 1 — mergeable
    under any CI gate that treats 1 as quality debt."""

    def test_corrupt_baseline_still_exits_2(self, tmp_path: Path) -> None:
        _project(tmp_path, f'aws_key = "{_SECRET}"')
        bad = tmp_path / "bad.json"
        bad.write_text("{ bad json", encoding="utf-8")
        assert _run(tmp_path, "all", "--baseline", str(bad)) == 2

    def test_without_a_baseline_it_also_exits_2(self, tmp_path: Path) -> None:
        _project(tmp_path, f'aws_key = "{_SECRET}"')
        assert _run(tmp_path, "all") == 2


class TestSubcommandsAgreeOnTheSecurityTier:
    """B-2/B-3: one corpus must not get different security verdicts depending on
    which subcommand or output format rendered it."""

    def test_traversal_exits_3_from_every_subcommand(self, tmp_path: Path) -> None:
        _project(tmp_path, "[x](/etc/passwd)")
        codes = {c: _run(tmp_path, c, "--quiet") for c in ("all", "links", "references")}
        assert set(codes.values()) == {3}, f"subcommands disagreed on a Z203: {codes}"

    def test_traversal_exits_3_from_every_supported_format(self, tmp_path: Path) -> None:
        _project(tmp_path, "[x](/etc/passwd)")
        codes = {f: _run(tmp_path, "all", "-f", f) for f in ("json", "sarif", "github-annotations")}
        assert set(codes.values()) == {3}, f"output format changed the verdict: {codes}"
