# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Three ways the security tier could be reached around rather than through.

All three were found by a read-only sweep and confirmed by execution, and all
three share one shape: a guarantee stated for the whole tier, implemented for
part of it.

**A leading ``../`` on an absolute href fell between both traversal branches.**
``if "../" in decoded_url`` claimed the link, then ``posixpath.join(base,
"/../etc/passwd")`` returned the absolute right operand and ``normpath`` ate the
``..`` at the root, leaving ``/etc/passwd`` — which does not start with ``..``,
so nothing was emitted and nothing continued. The ``elif`` that owns absolute
paths, and is the only branch that can raise ``Z203``, was never evaluated. Two
guards deferring to each other with conditions that do not partition.

**``excluded_dirs`` silenced ``Z202``/``Z203``/``Z205``.** The exclusion-immunity
fix routed the *credential* scan through ``iter_security_scan_sources`` and
stopped there: ``scan_security_findings`` yields only credential families and
``FORBIDDEN_TERM``. The other three security codes are produced by the link
pass, which runs over the user-scoped walk, so a ``javascript:`` link or a
traversal inside an excluded directory exited 0 while a credential in the same
file exited 2 — proving the file was reachable and only two fifths of the tier
reached it.

**``zenzic audit`` could not exit 2 or 3.** ``_evaluate_security_exit`` is
described as the single authority for the tier's exit code and routed at
fourteen sites in ``_check.py``; ``_audit.py`` never called it, and counted
breaches by *severity*, the exact test that function's own docstring documents
as unreliable.

The tests below are deliberately written as a matrix over the tier rather than
as three regressions, because the blind spot was never one missing case — it was
nineteen existing tests that all happened to use a credential.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.main import app


_SECRET = "AKIA" + "IOSFODNN7EXAMPLE"
_PROSE = "Prose long enough to clear the minimum word-count check comfortably here."

#: (payload, expected exit) — one per security code reachable from page content.
_TIER_PAYLOADS = [
    pytest.param(f'    aws_key = "{_SECRET}"', 2, id="Z201-credential"),
    pytest.param("[click](javascript:alert(1))", 2, id="Z205-forbidden-scheme"),
    pytest.param("[cfg](../../../../etc/passwd)", 3, id="Z203-relative-traversal"),
    pytest.param("[cfg](/etc/passwd)", 3, id="Z203-absolute-path"),
]


def _write(root: Path, rel: str, body: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"# Page\n\n{_PROSE}\n\n{body}\n", encoding="utf-8")


def _run(root: Path, monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    monkeypatch.chdir(root)
    return CliRunner().invoke(app, list(argv), catch_exceptions=False).exit_code


def _project(tmp_path: Path, *, excluded: str = "") -> Path:
    (tmp_path / "mkdocs.yml").write_text("site_name: Demo\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text(f'docs_dir = "docs"\n{excluded}\n', encoding="utf-8")
    (tmp_path / "docs").mkdir()
    _write(tmp_path, "docs/index.md", "Nothing to see here.")
    return tmp_path


class TestALeadingDotDotOnAnAbsolutePathIsStillATraversal:
    """``/etc/passwd`` and ``/../etc/passwd`` reach the same file."""

    @pytest.mark.parametrize(
        "href",
        [
            "/../etc/passwd",
            "/../../etc/passwd",
            "/../etc/../etc/passwd",
            "/..%2fetc%2fpasswd",
            "/..\\etc\\passwd",
        ],
    )
    def test_it_exits_3(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, href: str) -> None:
        root = _project(tmp_path)
        _write(root, "docs/page.md", f"[cfg]({href})")
        assert _run(root, monkeypatch, "check", "all", "--quiet") == 3, (
            f"'{href}' resolves to /etc/passwd and did not raise the non-suppressible Z203"
        )

    def test_the_plain_spelling_is_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Control: the branch that already worked must keep working."""
        root = _project(tmp_path)
        _write(root, "docs/page.md", "[cfg](/etc/passwd)")
        assert _run(root, monkeypatch, "check", "all", "--quiet") == 3

    def test_a_leading_dotdot_into_ordinary_content_is_not_fatal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Negative control: closing the gap must not promote every absolute path."""
        root = _project(tmp_path)
        _write(root, "docs/page.md", "[guide](/../guide/intro.md)")
        assert _run(root, monkeypatch, "check", "all", "--quiet") != 3


class TestExcludedDirsCannotSilenceAnyPartOfTheTier:
    """The matrix the original nineteen tests never crossed: exclusion × code."""

    @pytest.mark.parametrize(("payload", "expected"), _TIER_PAYLOADS)
    def test_every_security_code_survives_an_excluded_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: str, expected: int
    ) -> None:
        root = _project(tmp_path, excluded='excluded_dirs = ["vendor"]')
        _write(root, "docs/vendor/page.md", payload)
        assert _run(root, monkeypatch, "check", "all", "--quiet") == expected

    @pytest.mark.parametrize(("payload", "expected"), _TIER_PAYLOADS)
    def test_every_security_code_survives_an_excluded_file_pattern(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: str, expected: int
    ) -> None:
        root = _project(tmp_path, excluded='excluded_file_patterns = ["secret*.md"]')
        _write(root, "docs/secret-page.md", payload)
        assert _run(root, monkeypatch, "check", "all", "--quiet") == expected

    @pytest.mark.parametrize(("payload", "expected"), _TIER_PAYLOADS)
    def test_every_security_code_survives_a_cli_exclusion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: str, expected: int
    ) -> None:
        root = _project(tmp_path)
        _write(root, "docs/vendor/page.md", payload)
        code = _run(root, monkeypatch, "check", "all", "--exclude-dir", "vendor", "--quiet")
        assert code == expected

    def test_quality_findings_stay_excluded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Negative control: only the security tier pierces exclusions."""
        root = _project(tmp_path, excluded='excluded_dirs = ["vendor"]')
        _write(root, "docs/vendor/page.md", "[broken](does-not-exist.md)")
        assert _run(root, monkeypatch, "check", "all", "--quiet") == 0


class TestAuditHonoursTheExitCodeContract:
    """`audit` is the command whose name promises it; it was the one bypassing it."""

    # `audit` has no --quiet. Passing one is a *usage error*, and since the
    # UsageError remap is scoped to cli_main, an in-process CliRunner sees
    # Click's native exit 2 — which silently matched the expected value for two
    # of these cases. The first draft of this test passed for that reason.
    @pytest.mark.parametrize(("payload", "expected"), _TIER_PAYLOADS)
    def test_audit_reports_the_tier_exit_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: str, expected: int
    ) -> None:
        root = _project(tmp_path)
        _write(root, "docs/page.md", payload)
        assert _run(root, monkeypatch, "audit", "--format", "json") == expected

    def test_audit_still_exits_1_on_an_ordinary_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Negative control: the tier's codes must not swallow the quality tier."""
        root = _project(tmp_path)
        _write(root, "docs/page.md", "[broken](does-not-exist.md)")
        assert _run(root, monkeypatch, "audit", "--format", "json") == 1

    def test_a_flag_audit_does_not_have_is_a_usage_error_not_a_breach(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pins the trap above so a later reader does not fall into it again."""
        root = _project(tmp_path)
        _write(root, "docs/page.md", "Nothing here.")
        assert _run(root, monkeypatch, "audit", "--quiet") == 2
