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


_MONO_MAIN = """\
site_name: Monorepo Demo
plugins:
  - monorepo
nav:
  - Home: index.md
  - '!include projects/sub/mkdocs.yml'
"""
_MONO_SUB = """\
site_name: Sub
docs_dir: docs
nav:
  - Leak: leak.md
"""


def _monorepo(tmp_path: Path, sub_body: str) -> None:
    """A minimal mkdocs-monorepo project whose sub-project docs tree lives
    OUTSIDE the main docs_root, with the leak file excluded by pattern."""
    (tmp_path / "mkdocs.yml").write_text(_MONO_MAIN, encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text(
        'excluded_file_patterns = ["leak.md"]\n', encoding="utf-8"
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text(f"# Home\n\n{_PROSE}\n", encoding="utf-8")
    sub = tmp_path / "projects" / "sub" / "docs"
    sub.mkdir(parents=True)
    (tmp_path / "projects" / "sub" / "mkdocs.yml").write_text(_MONO_SUB, encoding="utf-8")
    (sub / "leak.md").write_text(f"# Sub\n\n{_PROSE}\n\n{sub_body}\n", encoding="utf-8")


class TestContentRoots:
    """The security tier must reach files in extra content roots (mkdocs monorepo)
    outside docs_root, even when user scoping excludes them — same guarantee the
    d1fbe21 fix gave docs_root, which it initially left incomplete for content roots.
    """

    def test_check_references_reports_credential_in_excluded_subproject(
        self, tmp_path: Path
    ) -> None:
        _monorepo(tmp_path, f'aws_key = "{_SECRET}"')
        result = CliRunner().invoke(
            app,
            ["check", "references", str(tmp_path / "docs"), "--no-header"],
            catch_exceptions=False,
        )
        assert result.exit_code == 2, (
            "a credential in an excluded monorepo sub-project doc escaped the "
            f"security scan — got {result.exit_code}:\n{result.output}"
        )

    def test_guard_scan_covers_monorepo_content_roots(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _monorepo(tmp_path, f'aws_key = "{_SECRET}"')
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(app, ["guard", "scan"], catch_exceptions=False)
        assert result.exit_code == 2, (
            "guard scan reported clean over a credential in an excluded monorepo "
            f"sub-project — got {result.exit_code}:\n{result.output}"
        )


class TestLocaleRoots:
    """No shipped adapter returns non-empty locale roots, so this is proven at the
    engine boundary: when a caller supplies locale_roots, a user-excluded file in
    one must still be security-scanned."""

    def test_excluded_locale_file_still_security_scanned(self, tmp_path: Path) -> None:
        from zenzic.core.exclusion import LayeredExclusionManager
        from zenzic.core.scanner import scan_docs_references
        from zenzic.models.config import ZenzicConfig

        (tmp_path / "mkdocs.yml").write_text("site_name: Demo\n", encoding="utf-8")
        (tmp_path / ".zenzic.toml").write_text(
            'docs_dir = "docs"\nexcluded_file_patterns = ["page.md"]\n', encoding="utf-8"
        )
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text(f"# Home\n\n{_PROSE}\n", encoding="utf-8")
        locale = tmp_path / "i18n" / "it"
        locale.mkdir(parents=True)
        (locale / "page.md").write_text(
            f'# IT\n\n{_PROSE}\n\naws_key = "{_SECRET}"\n', encoding="utf-8"
        )

        cfg, _ = ZenzicConfig.load(tmp_path)
        mgr = LayeredExclusionManager(cfg, repo_root=tmp_path, docs_root=docs)
        reports, _ = scan_docs_references(
            docs, mgr, repo_root=tmp_path, config=cfg, locale_roots=[(locale, "it")]
        )
        sec = [f.secret_type for r in reports for f in r.security_findings]
        assert sec, (
            "a credential in an excluded locale root escaped the security scan; "
            f"reports carried no security findings ({len(reports)} report(s))"
        )


class TestEmptyCorpusShortcut:
    """A corpus with *no* unexcluded file must not take a shortcut past exit 2.

    ``check all``'s text path prints ``Z906 NO_FILES_FOUND — Audit skipped.``
    and returns when the visible page count is zero. That was correct before the
    security-only pass existed: an all-excluded tree genuinely produced no
    findings. It now can, and the shortcut sits upstream of the exit-code
    evaluation, so the default human invocation reported **exit 0** over a live
    credential while ``--quiet`` and ``--format json`` both correctly reported 2.

    Every other fixture in this module happens to leave one unexcluded page, so
    the page count is never zero and this path was never exercised — the gap was
    in the suite, not only in the code.
    """

    def _only_excluded(self, tmp_path: Path) -> None:
        (tmp_path / "mkdocs.yml").write_text("site_name: Demo\n", encoding="utf-8")
        (tmp_path / ".zenzic.toml").write_text(
            'docs_dir = "docs"\nexcluded_dirs = ["private"]\n', encoding="utf-8"
        )
        page = tmp_path / "docs" / "private" / "leak.md"
        page.parent.mkdir(parents=True)
        page.write_text(f'# Leak\n\n{_PROSE}\n\naws_key = "{_SECRET}"\n', encoding="utf-8")

    def test_text_mode_does_not_skip_the_audit_past_a_breach(self, tmp_path: Path) -> None:
        self._only_excluded(tmp_path)
        exit_code, output = _check_all(tmp_path)
        assert exit_code == 2, (
            "the default text invocation took the Z906 'Audit skipped' shortcut past a "
            f"live credential — got {exit_code}:\n{output}"
        )

    def test_quiet_and_json_agree_with_text_mode(self, tmp_path: Path) -> None:
        """All three output modes must give one answer for one corpus."""
        self._only_excluded(tmp_path)
        quiet_code, _ = _check_all(tmp_path, "--quiet")
        json_code, _ = _check_all(tmp_path, "-f", "json")
        text_code, _ = _check_all(tmp_path)
        assert quiet_code == json_code == text_code == 2, (
            f"output mode changed the exit code: text={text_code} quiet={quiet_code} "
            f"json={json_code} — the security tier must not depend on formatting"
        )


class TestInlineHtmlSuppressionCannotHideTraversal:
    """``data-zenzic-ignore`` must not silence the path-traversal tier.

    The URP link loop opened with ``if link.suppressed: continue``, and
    ``link.suppressed`` comes from one place only: a ``data-zenzic-ignore``
    attribute written into the document under scan. Everything downstream of
    that skip included the Z202/Z203 emission block — the only site in the
    codebase that constructs either code, reached by both ``zenzic check`` and
    the LSP. So a page could silence its own path traversal, including
    ``Z203``, the sole Exit-3 code in the contract, by adding an attribute to
    its own anchor.

    The sibling code already had the right ordering: ``validator.py`` states
    that Z205 is checked *before* ``data-zenzic-ignore``, and the Z205 emitter
    duly ignores the attribute. Z202/Z203 never got the same treatment — a
    guard applied at some decision points but not all.

    Non-security codes must keep honouring the attribute, which the Z105 case
    below pins: the fix must not turn a suppression mechanism off wholesale.
    """

    def _page(self, tmp_path: Path, anchor: str) -> Path:
        (tmp_path / "mkdocs.yml").write_text("site_name: Demo\n", encoding="utf-8")
        (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n', encoding="utf-8")
        docs = tmp_path / "docs"
        docs.mkdir()
        page = docs / "index.md"
        page.write_text(f"# Page\n\n{_PROSE}\n\n{anchor}\n", encoding="utf-8")
        return page

    def test_data_zenzic_ignore_cannot_suppress_z203(self, tmp_path: Path) -> None:
        self._page(tmp_path, '<a href="../../../../etc/passwd" data-zenzic-ignore>x</a>')
        exit_code, output = _check_all(tmp_path)
        assert exit_code == 3, (
            "a document silenced its own path-traversal incident with an inline HTML "
            f"attribute — Z203 is the sole Exit-3 code and is never suppressible; got "
            f"{exit_code}:\n{output}"
        )

    def test_the_control_still_reports_without_the_attribute(self, tmp_path: Path) -> None:
        self._page(tmp_path, '<a href="../../../../etc/passwd">x</a>')
        exit_code, _ = _check_all(tmp_path)
        assert exit_code == 3, "the unsuppressed control must report Z203"

    def test_non_security_codes_still_honour_the_attribute(self, tmp_path: Path) -> None:
        """The negative control: Z105 must stay suppressible.

        Absolute-path links emit Z203 when the target looks like a system path
        and Z105 otherwise, from the same branch — so the fix has to separate
        the tier from its neighbour rather than disabling the skip wholesale.
        """
        self._page(tmp_path, '<a href="/some/site/path" data-zenzic-ignore>x</a>')
        exit_code, output = _check_all(tmp_path)
        assert "Z105" not in output, (
            "data-zenzic-ignore stopped suppressing a non-security code; the security "
            f"carve-out must be narrow:\n{output}"
        )


class TestGuardScanFailsClosedOnUnreadableFiles:
    """A file the secret gate cannot read is not a file without secrets.

    ``_scan_file_for_secrets`` caught ``OSError`` and returned an empty finding
    list, which is indistinguishable from "this file is clean" — and the summary
    counted it via ``len(targets)``, so an unreadable file was reported as
    *scanned*. A repository with one unreadable document therefore produced
    "Secret Guard clean: N file(s) scanned, no secrets detected" and **exit 0**
    from the gate that stands between a leak and a commit.

    Fail-closed is the only safe direction here: the gate must say what it could
    not verify and exit non-zero, rather than report a clean bill it did not earn.
    """

    def _repo(self, tmp_path: Path) -> Path:
        (tmp_path / "mkdocs.yml").write_text("site_name: Demo\n", encoding="utf-8")
        (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n', encoding="utf-8")
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text(f"# Home\n\n{_PROSE}\n", encoding="utf-8")
        secret = docs / "secret.md"
        secret.write_text(f'# Leak\n\n{_PROSE}\n\naws_key = "{_SECRET}"\n', encoding="utf-8")
        return secret

    def test_unreadable_file_does_not_report_clean(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret = self._repo(tmp_path)
        secret.chmod(0o000)
        try:
            monkeypatch.chdir(tmp_path)
            result = CliRunner().invoke(app, ["guard", "scan"], catch_exceptions=False)
            assert result.exit_code != 0, (
                "the secret gate reported a clean bill over a file it could not read — "
                f"got exit {result.exit_code}:\n{result.output}"
            )
            assert "Secret Guard clean" not in result.output, (
                f"output claims cleanliness it did not verify:\n{result.output}"
            )
            assert "could not read" in result.output, (
                f"the gate must say what it failed to verify:\n{result.output}"
            )
        finally:
            secret.chmod(0o644)

    def test_readable_repo_still_reports_clean(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Negative control: the fix must not make every clean repo fail."""
        secret = self._repo(tmp_path)
        secret.unlink()  # leave only the clean page
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(app, ["guard", "scan"], catch_exceptions=False)
        assert result.exit_code == 0, (
            f"a fully readable, secret-free repo must still pass: {result.output}"
        )


class TestCheckLinksCoversContentRoots:
    """``check links`` must sweep the same trees its siblings do.

    ``iter_security_scan_sources``' own contract says the security scan must
    cover *every* tree ``scan_docs_references`` reaches. ``check links`` computed
    ``locale_roots`` and passed it, but never computed ``content_roots`` — the
    one subcommand of nine that did not — so an MkDocs monorepo's included
    sub-project docs were outside its scan entirely. Since ``check links`` does
    surface security findings, that produced a user-visible split: exit 2 under
    ``check all`` and exit 0 under ``check links``, on one repository.
    """

    def test_check_links_reports_credential_in_monorepo_subproject(self, tmp_path: Path) -> None:
        _monorepo(tmp_path, f'aws_key = "{_SECRET}"')
        result = CliRunner().invoke(
            app,
            ["check", "links", str(tmp_path / "docs"), "--no-header"],
            catch_exceptions=False,
        )
        assert result.exit_code == 2, (
            "check links did not sweep the monorepo content root its siblings sweep — "
            f"got {result.exit_code}:\n{result.output}"
        )

    def test_check_all_and_check_links_agree(self, tmp_path: Path) -> None:
        """One repository must not get two answers depending on the subcommand."""
        _monorepo(tmp_path, f'aws_key = "{_SECRET}"')
        all_code = (
            CliRunner()
            .invoke(
                app, ["check", "all", str(tmp_path / "docs"), "--no-header"], catch_exceptions=False
            )
            .exit_code
        )
        links_code = (
            CliRunner()
            .invoke(
                app,
                ["check", "links", str(tmp_path / "docs"), "--no-header"],
                catch_exceptions=False,
            )
            .exit_code
        )
        assert all_code == links_code == 2, (
            f"subcommand changed the security verdict: check all={all_code}, "
            f"check links={links_code}"
        )
