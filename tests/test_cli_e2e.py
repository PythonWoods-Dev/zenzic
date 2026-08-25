# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""End-to-end CLI tests for Zenzic security exit-code contract.

These tests exercise the **full** CLI pipeline — no mocks on the scanner,
validator, or reporter.  They verify the documented exit-code contract:

    Exit 0 — all checks passed
    Exit 1 — general failures (broken links, syntax errors, …)
    Exit 2 — credential scanner detection (NEVER suppressed by --exit-zero)
    Exit 3 — path traversal guard system-path traversal (NEVER suppressed)

Gap closed: ``docs/internal/arch_gaps.md`` § "Security Pipeline Coverage".
"""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.main import app


runner = CliRunner()

_TRAVERSAL_SANDBOX = Path(__file__).resolve().parent / "sandboxes" / "screenshot_traversal"


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_sandbox(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a minimal Zenzic project in *tmp_path*.

    Writes ``.zenzic.toml`` and the given *files* (paths relative to the
    sandbox root).  Returns the sandbox root.
    """
    toml = tmp_path / ".zenzic.toml"
    toml.write_text(
        textwrap.dedent("""\
            docs_dir = "docs"

            [build_context]
            engine = "mkdocs"
        """),
        encoding="utf-8",
    )
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(content), encoding="utf-8")
    return tmp_path


# ── Path Traversal Guard — Exit 3 (system-path traversal) ────────────────────


class TestPathTraversalGuardE2E:
    """Path traversal guard must exit 3 on system-path traversal."""

    def test_path_traversal_guard_sandbox_exits_3(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """check all on the traversal sandbox triggers Exit 3."""
        sandbox = tmp_path / "traversal"
        shutil.copytree(_TRAVERSAL_SANDBOX, sandbox)
        monkeypatch.chdir(sandbox)

        result = runner.invoke(app, ["check", "all"])

        assert result.exit_code == 3, (
            f"Expected exit 3 (security_incident), got {result.exit_code}.\n"
            f"Output:\n{result.stdout}"
        )
        assert (
            "PATH_TRAVERSAL" in result.stdout or "Z202" in result.stdout or "Z203" in result.stdout
        )

    def test_path_traversal_guard_exit_3_not_suppressed_by_exit_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--exit-zero must NOT suppress Exit 3 — documented contract."""
        sandbox = tmp_path / "traversal"
        shutil.copytree(_TRAVERSAL_SANDBOX, sandbox)
        monkeypatch.chdir(sandbox)

        result = runner.invoke(app, ["check", "all", "--exit-zero"])

        assert result.exit_code == 3, (
            f"--exit-zero must not suppress Exit 3 (security_incident), "
            f"got {result.exit_code}.\nOutput:\n{result.stdout}"
        )


# ── Credential Breach — Exit 2 (credential leak) ────────────────────────────────


class TestCredentialBreachE2E:
    """Credential scanner must exit 2 when a credential is detected."""

    _BREACH_DOC = """\
        # Cloud Setup

        This page documents the initial cloud provider configuration steps
        for the deployment pipeline.  Follow the instructions carefully.

        ## Provider Credentials

        Refer to the provisioning guide for credential rotation procedures
        and the secret management policy before deploying to production.

        [AWS Dashboard](https://console.aws.amazon.com?key=AKIA1234567890ABCDEF)
    """

    def test_credential_scanner_breach_exits_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """check all exits 2 when an AWS key is embedded in a link URL."""
        _make_sandbox(tmp_path, {"docs/index.md": self._BREACH_DOC})
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "all"])

        assert result.exit_code == 2, (
            f"Expected exit 2 (security_breach), got {result.exit_code}.\nOutput:\n{result.stdout}"
        )
        assert "ZENZIC" in (result.stdout + result.stderr)

    def test_credential_scanner_exit_2_not_suppressed_by_exit_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--exit-zero must NOT suppress Exit 2 — documented contract."""
        _make_sandbox(tmp_path, {"docs/index.md": self._BREACH_DOC})
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "all", "--exit-zero"])

        assert result.exit_code == 2, (
            f"--exit-zero must not suppress Exit 2 (security_breach), "
            f"got {result.exit_code}.\nOutput:\n{result.stdout}"
        )


# ── Forbidden Scheme — Exit 2 (Z205, part of the Tier-0 "never suppressible" set) ──


class TestForbiddenSchemeE2E:
    """Z205 FORBIDDEN_SCHEME must exit 2 — it is listed alongside Z201/Z204 in
    the Tier-0 invariant "Exit 2: Credential Scanner Breach (Z201, Z204, Z205).
    Never suppressible." Regression for: Z205 is detected by a rule check (not
    the credential-scanner bridge in ``_map_credential_to_finding``), so its
    ``Finding.severity`` was derived from ``CodeDefinition.severity`` via
    ``_finding_severity()`` — which returns the raw catalog value ``"error"``
    for Z205 instead of ``"security_breach"``, since only Z203 has a special
    case in that function. The result: Z205 was exiting 1, not 2, and was
    exposed to the same suppression machinery as an ordinary error.
    """

    _FORBIDDEN_SCHEME_DOC = """\
        # Interactive Widget

        This page embeds a widget link using a scheme that must never be
        permitted in published documentation, regardless of context.

        <a href="javascript:alert(document.cookie)">Click for details</a>
    """

    def test_forbidden_scheme_exits_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """check all exits 2 when a javascript: scheme href is present."""
        _make_sandbox(tmp_path, {"docs/index.md": self._FORBIDDEN_SCHEME_DOC})
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "all"])

        assert result.exit_code == 2, (
            f"Z205 must exit 2 (security_breach) per the Tier-0 'Z201, Z204, "
            f"Z205 — never suppressible' contract, got {result.exit_code}.\n"
            f"Output:\n{result.stdout}"
        )
        assert "SECURITY BREACH DETECTED" in result.stdout
        assert "forbidden scheme 'javascript:' detected" in result.stdout

    def test_forbidden_scheme_exit_2_not_suppressed_by_exit_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--exit-zero must NOT suppress Z205's Exit 2 — documented contract."""
        _make_sandbox(tmp_path, {"docs/index.md": self._FORBIDDEN_SCHEME_DOC})
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "all", "--exit-zero"])

        assert result.exit_code == 2, (
            f"--exit-zero must not suppress Z205's Exit 2 (security_breach), "
            f"got {result.exit_code}.\nOutput:\n{result.stdout}"
        )


# ── check links — Exit 2 gap (single-subcommand parity with check_all) ──────


class TestCheckLinksSecurityBreachExitCodeE2E:
    """``zenzic check links`` must exit 2 on a security_breach finding, in
    every output format — same contract ``check_all`` already honors.

    Regression for: check_links' four output branches (json, sarif,
    github-annotations, text) each only checked ``severity == "security_incident"``
    (Exit 3) and ``severity == "error"`` (Exit 1) before returning/raising —
    none of them checked ``severity == "security_breach"`` at all, so a Z205
    finding (FORBIDDEN_SCHEME, in link_codes and therefore routed through
    check_links) fell through to Exit 1 instead of the Tier-0-mandated Exit 2.
    Discovered during V031_PRE_RELEASE_FINAL_CLOSURE while auditing check_all's
    blast radius for the Z205 severity fix; not fixed there per that
    directive's declared scope. Fixed here.
    """

    _FORBIDDEN_SCHEME_DOC = TestForbiddenSchemeE2E._FORBIDDEN_SCHEME_DOC

    def test_check_links_text_exits_2_on_breach(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _make_sandbox(tmp_path, {"docs/index.md": self._FORBIDDEN_SCHEME_DOC})
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "links"])

        assert result.exit_code == 2, (
            f"check links (text) must exit 2 on a Z205 security_breach finding, "
            f"got {result.exit_code}.\nOutput:\n{result.stdout}"
        )

    def test_check_links_json_exits_2_on_breach(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _make_sandbox(tmp_path, {"docs/index.md": self._FORBIDDEN_SCHEME_DOC})
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "links", "--format", "json"])

        assert result.exit_code == 2, (
            f"check links --format json must exit 2 on a Z205 security_breach "
            f"finding, got {result.exit_code}.\nOutput:\n{result.stdout}"
        )

    def test_check_links_sarif_exits_2_on_breach(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _make_sandbox(tmp_path, {"docs/index.md": self._FORBIDDEN_SCHEME_DOC})
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "links", "--format", "sarif"])

        assert result.exit_code == 2, (
            f"check links --format sarif must exit 2 on a Z205 security_breach "
            f"finding, got {result.exit_code}.\nOutput:\n{result.stdout}"
        )

    def test_check_links_github_annotations_exits_2_on_breach(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _make_sandbox(tmp_path, {"docs/index.md": self._FORBIDDEN_SCHEME_DOC})
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "links", "--format", "github-annotations"])

        assert result.exit_code == 2, (
            f"check links --format github-annotations must exit 2 on a Z205 "
            f"security_breach finding, got {result.exit_code}.\nOutput:\n{result.stdout}"
        )


# ── check links / check placeholders — Credential Scanner Wiring Gap ────────


class TestCheckLinksPlaceholdersCredentialScanE2E:
    """``zenzic check links`` and ``zenzic check placeholders`` must invoke the
    credential scanner and exit 2 on a Z201 breach, in parity with
    ``check_all``/``check_references``.

    Regression for: both subcommands already call scan_docs_references()
    (check_placeholders directly, check_links via validate_links_structured())
    -- the credential scanner runs on every file, every time, as part of that
    pipeline's harvest() pass -- but neither subcommand ever reads the
    resulting IntegrityReport.security_findings, so a real credential leak
    produced zero signal and an ordinary exit 0/1 through these two entry
    points, silently violating the Tier-0 "Exit 2: Credential Scanner Breach
    -- Never suppressible" contract. Discovered during
    V031_CHECK_LINKS_PLACEHOLDERS_EXIT2_GAP (2026-08-24), fixed here
    (V031_EXIT2_WIRING_AND_Z406_ADAPTER_AGNOSTICISM_CHECK, 2026-08-25) --
    the fix costs no extra scan time, since the scan already ran; it only
    adds a loop over already-computed security_findings, mirroring
    check_all's existing _map_credential_to_finding pattern.
    """

    _BREACH_DOC = TestCredentialBreachE2E._BREACH_DOC

    def test_check_links_exits_2_on_credential_breach(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _make_sandbox(tmp_path, {"docs/index.md": self._BREACH_DOC})
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "links"])

        assert result.exit_code == 2, (
            f"check links must exit 2 on a Z201 security_breach finding, "
            f"got {result.exit_code}.\nOutput:\n{result.stdout}"
        )

    def test_check_placeholders_exits_2_on_credential_breach(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _make_sandbox(tmp_path, {"docs/index.md": self._BREACH_DOC})
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "placeholders"])

        assert result.exit_code == 2, (
            f"check placeholders must exit 2 on a Z201 security_breach finding, "
            f"got {result.exit_code}.\nOutput:\n{result.stdout}"
        )


# ── --exit-zero suppresses Exit 1 (general errors) ──────────────────────────


class TestExitZeroContractE2E:
    """--exit-zero suppresses general failures but not security exits."""

    _BROKEN_LINK_DOC = """\
        # Home

        This page contains a broken link to exercise the general failure
        exit path.  The target file does not exist in this sandbox.

        [Broken](this-page-does-not-exist.md)
    """

    def test_broken_link_exits_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """check all exits 1 on a broken link (baseline)."""
        _make_sandbox(tmp_path, {"docs/index.md": self._BROKEN_LINK_DOC})
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "all"])

        assert result.exit_code == 1, (
            f"Expected exit 1 (general failure), got {result.exit_code}.\nOutput:\n{result.stdout}"
        )

    def test_exit_zero_suppresses_exit_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--exit-zero must suppress Exit 1 (broken links)."""
        _make_sandbox(tmp_path, {"docs/index.md": self._BROKEN_LINK_DOC})
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "all", "--exit-zero"])

        assert result.exit_code == 0, (
            f"--exit-zero should suppress Exit 1, got {result.exit_code}.\nOutput:\n{result.stdout}"
        )

    def test_clean_sandbox_exits_0(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A clean sandbox with no issues exits 0."""
        _make_sandbox(
            tmp_path,
            {
                "docs/index.md": """\
                    # Welcome

                    This is a perfectly valid documentation page with enough words
                    to pass the placeholder check.  It contains no broken links,
                    no credentials, and no path traversal attempts.  The content
                    is intentionally verbose to exceed the minimum word count
                    threshold enforced by the short-content scanner.
                """,
            },
        )
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "all"])

        assert result.exit_code == 0, (
            f"Expected exit 0 (clean), got {result.exit_code}.\nOutput:\n{result.stdout}"
        )
        assert "Analysis complete" in result.stdout


# ── Priority: Exit 3 wins over Exit 2 ───────────────────────────────────────


class TestExitCodePriorityE2E:
    """When both security_incident and security_breach coexist, Exit 3 wins."""

    def test_exit_3_beats_exit_2(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exit 3 (path traversal guard) takes priority over Exit 2 (credential scanner breach)."""
        _make_sandbox(
            tmp_path,
            {
                "docs/index.md": """\
                    # Dual Threat

                    This page has both a system-path traversal and a leaked
                    credential to verify the exit-code priority contract.

                    [Host](../../../../etc/shadow)

                    [AWS](https://console.aws.amazon.com?key=AKIA1234567890ABCDEF)
                """,
            },
        )
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "all"])

        assert result.exit_code == 3, (
            f"Exit 3 (security_incident) must beat Exit 2 (security_breach), "
            f"got {result.exit_code}.\nOutput:\n{result.stdout}"
        )


# ── --format json on individual check commands ──────────────────────────────


class TestJsonFormatE2E:
    """--format json outputs structured JSON on individual check commands."""

    def test_check_links_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """check links --format json outputs valid JSON with findings/summary keys."""
        _make_sandbox(
            tmp_path,
            {"docs/index.md": "# Hello\n\nEnough words to not be a placeholder for the scanner."},
        )
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "links", "--format", "json"])

        assert result.exit_code == 0
        import json

        data = json.loads(result.stdout)
        assert "findings" in data
        assert "summary" in data
        assert "errors" in data["summary"]
        assert "elapsed_seconds" in data["summary"]

    def test_check_orphans_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """check orphans --format json outputs valid JSON."""
        _make_sandbox(
            tmp_path, {"docs/index.md": "# Home\n\nWords words words words words words words."}
        )
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "orphans", "--format", "json"])

        assert result.exit_code == 0
        import json

        data = json.loads(result.stdout)
        assert "findings" in data
        assert "summary" in data

    def test_check_snippets_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """check snippets --format json outputs valid JSON."""
        _make_sandbox(tmp_path, {"docs/index.md": "# Home\n\nWords words words."})
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "snippets", "--format", "json"])

        assert result.exit_code == 0
        import json

        data = json.loads(result.stdout)
        assert "findings" in data
        assert "summary" in data

    def test_check_references_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """check references --format json outputs valid JSON."""
        _make_sandbox(tmp_path, {"docs/index.md": "# Home\n\nWords words words."})
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "references", "--format", "json"])

        assert result.exit_code == 0
        import json

        data = json.loads(result.stdout)
        assert "findings" in data
        assert "summary" in data

    def test_check_assets_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """check assets --format json outputs valid JSON."""
        _make_sandbox(tmp_path, {"docs/index.md": "# Home\n\nWords words words."})
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "assets", "--format", "json"])

        assert result.exit_code == 0
        import json

        data = json.loads(result.stdout)
        assert "findings" in data
        assert "summary" in data

    def test_check_links_json_exit_code_on_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """check links --format json still exits 1 on broken links."""
        _make_sandbox(tmp_path, {"docs/index.md": "# Home\n\n[Broken](nope.md)"})
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "links", "--format", "json"])

        assert result.exit_code == 1
        import json

        data = json.loads(result.stdout)
        assert data["summary"]["errors"] > 0
        assert len(data["findings"]) > 0


class TestSuppressionCapE2E:
    """Release A CAP contract: 30 allowed, 31 blocks with guidance."""

    @staticmethod
    def _make_cap_sandbox(tmp_path: Path, inline_count: int, cap: int = 30) -> Path:
        toml = tmp_path / ".zenzic.toml"
        toml.write_text(
            textwrap.dedent(
                """\
                docs_dir = "docs"

                [build_context]
                engine = "standalone"

                [governance]
                suppression_cap = {cap}
                suppression_cap_fail_hard = true
                """
            ).format(cap=cap),
            encoding="utf-8",
        )

        suppressions = "\n".join(
            f"Allowed historical note {i}. <!-- zenzic:ignore: Z601 - test -->"
            for i in range(1, inline_count + 1)
        )
        page = tmp_path / "docs" / "index.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            "# CAP test\n\n"
            "This page exists only to validate suppression CAP behavior under Release A.\n\n"
            "This fixture includes a long neutral paragraph so quality checks stay stable across "
            "runs and the assertions focus only on governance behavior. The paragraph explains "
            "that the document is synthetic, contains no external links, and exists only for test "
            "determinism. It intentionally uses ordinary language and avoids reserved keywords "
            "that might be interpreted as unfinished documentation markers.\n\n"
            f"{suppressions}\n",
            encoding="utf-8",
        )
        return tmp_path

    def test_cap_30_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exactly 30 active suppressions must pass."""
        self._make_cap_sandbox(tmp_path, inline_count=30)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "all"])

        assert result.exit_code == 0, (
            f"Expected exit 0 at CAP boundary (30/30), got {result.exit_code}.\n"
            f"Output:\n{result.stdout}"
        )
        assert "Suppression Audit:" in result.stdout
        assert "30/30" in result.stdout

    def test_cap_31_fails_with_playbook_guidance(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """31st suppression must fail hard with a clear remediation link."""
        self._make_cap_sandbox(tmp_path, inline_count=31)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "all"])

        assert result.exit_code == 1, (
            f"Expected exit 1 when CAP is exceeded (31/30), got {result.exit_code}.\n"
            f"Output:\n{result.stdout}"
        )
        assert "SUPPRESSION_CAP_EXCEEDED" in result.stdout
        assert "Total Active Suppressions:" in result.stdout
        assert "Configured Global CAP:" in result.stdout
        assert "31" in result.stdout
        assert "30" in result.stdout
        assert "release-governance-protocol" in result.stdout
        assert "HOTSPOTS - Top Offenders" in result.stdout

    def test_check_all_json_exposes_suppression_contract(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """JSON output must always include mandatory suppression contract fields."""
        self._make_cap_sandbox(tmp_path, inline_count=0)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "all", "--format", "json"])

        assert result.exit_code == 0
        import json

        data = json.loads(result.stdout)
        assert data["suppression_count"] == 0
        assert data["suppression_cap"] == 30
        assert data["suppression_debt_pts"] == 0
        assert data["debt_status"] == "CLEAN"

    def test_cap_exceeded_json_exposes_suppression_contract(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CAP fail-hard JSON must include the same suppression contract fields."""
        self._make_cap_sandbox(tmp_path, inline_count=31)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "all", "--format", "json"])

        assert result.exit_code == 1
        import json

        data = json.loads(result.stdout)
        assert data["error"] == "SUPPRESSION_CAP_EXCEEDED"
        assert data["suppression_count"] == 31
        assert data["suppression_cap"] == 30
        assert data["suppression_debt_pts"] == 1
        assert data["debt_status"] == "CRITICAL"

    def test_extended_debt_tag_visible_when_cap_raised(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CAP above sovereign default prints EXTENDED DEBT marker in footer."""
        self._make_cap_sandbox(tmp_path, inline_count=30, cap=45)
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ["check", "all"])

        assert result.exit_code == 0, (
            f"Expected exit 0 at 30/45, got {result.exit_code}.\nOutput:\n{result.stdout}"
        )
        assert "Suppression Audit:" in result.stdout
        assert "30/45" in result.stdout
        assert "[EXTENDED DEBT]" in result.stdout

    def test_per_file_ignores_suppress_targeted_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Per-file ignore must suppress matching findings in check all output."""
        toml = tmp_path / ".zenzic.toml"
        toml.write_text(
            textwrap.dedent(
                """\
                docs_dir = "docs"

                [build_context]
                engine = "standalone"

                [governance]
                suppression_cap = 30
                suppression_cap_fail_hard = true

                [governance.per_file_ignores]
                "docs/index.md" = ["Z101"]
                """
            ),
            encoding="utf-8",
        )
        p = tmp_path / "docs" / "index.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "# Per-file ignore test\n\n"
            "This page intentionally has a broken local link to validate suppression.\n\n"
            "[Broken](missing-page.md)\n",
            encoding="utf-8",
        )

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["check", "all"])

        assert result.exit_code == 0, (
            "Expected per-file ignore to suppress Z101 in this file. "
            f"Got exit {result.exit_code}.\nOutput:\n{result.stdout}"
        )
        assert "Suppression Audit:" in result.stdout
        assert "per-file: 1" in result.stdout

    def test_directory_policies_filter_findings_zero_debt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """directory_policies must filter matching findings with zero suppression debt."""
        toml = tmp_path / ".zenzic.toml"
        toml.write_text(
            textwrap.dedent(
                """\
                docs_dir = "docs"

                [build_context]
                engine = "standalone"

                [governance]
                suppression_cap = 30
                suppression_cap_fail_hard = true
                brand_obsolescence = ["OldBrand"]

                [governance.directory_policies]
                "docs/index.md" = ["Z601"]
                """
            ),
            encoding="utf-8",
        )
        p = tmp_path / "docs" / "index.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            "# Directory policy test\n\n"
            "This page mentions OldBrand which triggers Z601.\n\n"
            "It also contains enough words to avoid triggering Z502 short-content warnings. "
            "The directory_policies feature introduced in ADR-084 allows strategic exemptions "
            "with zero suppression debt cost, unlike per_file_ignores which costs one point. "
            "This is the primary difference between the two governance mechanisms.\n",
            encoding="utf-8",
        )

        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["check", "all", "--format", "json"])

        assert result.exit_code == 0, (
            "Expected directory_policy to suppress Z601 finding. "
            f"Got exit {result.exit_code}.\nOutput:\n{result.stdout}"
        )
        import json

        data = json.loads(result.stdout)
        # Finding must be absent (dropped silently)
        assert data["suppression_count"] == 0, (
            f"directory_policies must contribute 0 debt, got {data['suppression_count']}"
        )
