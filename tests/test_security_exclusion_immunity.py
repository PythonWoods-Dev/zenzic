# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The security tier must not honor user-configured scope exclusions.

``excluded_file_patterns``, ``excluded_dirs`` and ``--exclude-dir`` prune files
from discovery before any scan runs, so a credential inside an excluded file
produced no Z201 at all: ``zenzic check all`` reported a clean exit 0 on a repo
containing a live key, and ``zenzic guard scan`` — the dedicated secret gate —
answered "no targets found". That contradicts the Exit Code Contract's "never
suppressible" guarantee: scoping a file out of *quality* analysis is legitimate
configuration, but the credential/forbidden-term scan (Z201/Z204) is the one
tier that must run regardless.

System guardrails and VCS-ignore remain honored even by the security pass:
gitignored content is deliberately outside the published corpus (and includes
operator-private directories), so "everything that ships gets the secret scan"
is the exact boundary — no narrower, no wider.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.lsp.server import LanguageServer
from zenzic.main import app


_SECRET = "AKIAIOSFODNN7EXAMPLE"
_PROSE = (
    "This page carries a comfortable amount of prose so the minimum word-count "
    "check stays quiet and only the finding under discussion is reported here."
)


def _project(tmp_path: Path, config_body: str, page_rel: str, page_body: str) -> Path:
    (tmp_path / "mkdocs.yml").write_text("site_name: Demo\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text(f'docs_dir = "docs"\n{config_body}', encoding="utf-8")
    page = tmp_path / "docs" / page_rel
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(f"# Page\n\n{_PROSE}\n\n{page_body}\n", encoding="utf-8")
    # A second, unexcluded page so the corpus is never empty on its own.
    (tmp_path / "docs" / "index.md").write_text(f"# Home\n\n{_PROSE}\n", encoding="utf-8")
    return page


def _check_all(tmp_path: Path, *extra: str) -> tuple[int, str]:
    result = CliRunner().invoke(
        app,
        ["check", "all", str(tmp_path / "docs"), "--no-header", *extra],
        catch_exceptions=False,
    )
    return result.exit_code, result.output


class TestCheckAll:
    def test_excluded_file_pattern_cannot_hide_a_credential(self, tmp_path: Path) -> None:
        _project(
            tmp_path,
            'excluded_file_patterns = ["guide.md"]\n',
            "guide.md",
            f"```bash\nexport AWS_KEY={_SECRET}\n```",
        )
        exit_code, output = _check_all(tmp_path)
        assert exit_code == 2, (
            f"a credential in a config-excluded file must still force exit 2 — got "
            f"{exit_code}:\n{output}"
        )

    def test_excluded_dirs_cannot_hide_a_credential(self, tmp_path: Path) -> None:
        _project(
            tmp_path,
            'excluded_dirs = ["private"]\n',
            "private/leak.md",
            f"```bash\nexport AWS_KEY={_SECRET}\n```",
        )
        exit_code, output = _check_all(tmp_path)
        assert exit_code == 2, f"excluded_dirs hid a credential — got {exit_code}:\n{output}"

    def test_cli_exclude_dir_flag_cannot_hide_a_credential(self, tmp_path: Path) -> None:
        _project(
            tmp_path,
            "",
            "private/leak.md",
            f"```bash\nexport AWS_KEY={_SECRET}\n```",
        )
        exit_code, output = _check_all(tmp_path, "--exclude-dir", "private")
        assert exit_code == 2, f"--exclude-dir hid a credential — got {exit_code}:\n{output}"

    def test_a_fully_excluded_corpus_still_reports_the_breach(self, tmp_path: Path) -> None:
        """The empty-corpus early return must not outrank the security pass."""
        _project(
            tmp_path,
            'excluded_file_patterns = ["*.md"]\n',
            "guide.md",
            f"```bash\nexport AWS_KEY={_SECRET}\n```",
        )
        exit_code, output = _check_all(tmp_path)
        assert exit_code == 2, (
            f"excluding every file returned 'clean' over a live credential — got "
            f"{exit_code}:\n{output}"
        )

    def test_exclusion_still_hides_quality_findings(self, tmp_path: Path) -> None:
        """The negative control: only the security tier ignores scoping.

        A credential-free excluded file with a genuine quality defect (a broken
        relative link) must stay excluded — the fix must not quietly re-enrol
        excluded files into the full scan.
        """
        _project(
            tmp_path,
            'excluded_file_patterns = ["guide.md"]\n',
            "guide.md",
            "See [missing](./does-not-exist.md).",
        )
        exit_code, output = _check_all(tmp_path)
        assert exit_code == 0, (
            f"an excluded file's quality findings leaked into the report — got "
            f"{exit_code}:\n{output}"
        )


class TestGuardScan:
    def test_guard_scan_ignores_user_exclusions(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _project(
            tmp_path,
            'excluded_file_patterns = ["guide.md"]\n',
            "guide.md",
            f"```bash\nexport AWS_KEY={_SECRET}\n```",
        )
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(app, ["guard", "scan"], catch_exceptions=False)
        assert result.exit_code == 2, (
            f"guard scan reported clean on an excluded file holding a live key — got "
            f"{result.exit_code}:\n{result.output}"
        )


class TestLspParity:
    def test_lsp_excluded_buffer_still_reports_security(self, tmp_path: Path) -> None:
        """An excluded file open in the editor shows Z201 and nothing else."""
        page = _project(
            tmp_path,
            'excluded_file_patterns = ["guide.md"]\n',
            "guide.md",
            f'aws_key = "{_SECRET}"\n\nSee [missing](./does-not-exist.md).',
        )

        server = LanguageServer()
        server.repo_root = tmp_path
        server._build_vsm_sync()

        uri = page.resolve().as_uri()
        server.handle_message(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {"textDocument": {"uri": uri, "text": page.read_text(encoding="utf-8")}},
            }
        )
        assert server.engine is not None and server.vsm is not None
        assert server.overlay is not None
        results = server.engine.process_changes(server.vsm, server.overlay, {uri})
        codes = {d.code for d in results.get(uri, [])}
        assert "Z201" in codes, (
            f"the editor shows no credential diagnostic for an excluded buffer the "
            f"CLI now reports (CLI/LSP security parity): {sorted(codes) or 'nothing'}"
        )
        assert not codes - {"Z201", "Z204"}, (
            f"quality diagnostics leaked into an excluded buffer — exclusion must "
            f"keep governing every non-security code: {sorted(codes)}"
        )
