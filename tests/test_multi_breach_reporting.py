# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Every Tier-0 security finding in a file must be reported, not just the first.

A priority-table row recorded a suspected "single-breach-per-run" detection gap:
a file containing both an AWS-style credential (``Z201``) and a ``javascript:``
link (``Z205``) appeared to report only one of the two, with no ``--only`` flag
involved. Re-running the exact fixture across the real commit history showed the
symptom was real but its cause was misidentified — and in the opposite direction
from the report:

    f1b624b (before the --only fix)   breaches=1  Z201=1  Z205=0  exit=2
    1cc2a1e (the --only fix)          breaches=1  Z201=1  Z205=0  exit=2
    c2d5810 (before the Z205 fix)     breaches=1  Z201=1  Z205=0  exit=2
    d990d19 (the Z205 Markdown fix)   breaches=2  Z201=1  Z205=1  exit=2

The credential was never the finding being dropped; ``Z205`` was, because it was
evaluated only inside the HTML-tag scanning loop and so never fired on a link
written in Markdown syntax. Nothing short-circuited after a first hit, and the
``--only`` filtering fix was unrelated. That gap is closed (``d990d19``).

These tests exist so the *reported* invariant — every security finding in a file
surfaces independently — is pinned by the suite rather than resting on the
absence of a bug nobody is checking for. The rows above are the red state: each
test below fails at ``c2d5810`` and passes from ``d990d19`` on.
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core.adapters import get_adapter
from zenzic.core.incremental import IncrementalAnalysisEngine
from zenzic.core.scanner import _build_rule_engine
from zenzic.models.config import ZenzicConfig


_PROSE = (
    "This page carries a comfortable amount of prose so the minimum word-count "
    "check stays quiet and only the finding under discussion is reported here."
)
_CREDENTIAL = 'aws_key = "AKIAIOSFODNN7EXAMPLE"'
_SECOND_CREDENTIAL = 'aws_alt = "AKIAJ2YQ4XKZPQR7ABCD"'
_MD_SCHEME = "[click me](javascript:alert(document.cookie))"
_HTML_SCHEME = '<a href="javascript:alert(1)">x</a>'


def _urp_codes(tmp_path: Path, body: str) -> list[str]:
    """Rule IDs the shared URP pass reports for a page built from *body*.

    Uses ``_run_urp_checks`` deliberately: it is the single emission site shared
    by the CLI (via ``scanner.py``) and the LSP, so a gap here would affect both.
    """
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    page = docs / "index.md"
    text = f"# Home\n\n{_PROSE}\n\n{body}\n"
    page.write_text(text, encoding="utf-8")
    config = ZenzicConfig(docs_dir=Path("docs"))
    engine = IncrementalAnalysisEngine(
        config=config,
        rule_engine=_build_rule_engine(config),
        adapter=get_adapter(config.build_context, docs, tmp_path),
        docs_root=docs,
        repo_root=tmp_path,
    )
    return [f.rule_id for f in engine._run_urp_checks(None, page, text)]


class TestSchemeAndCredentialCoexist:
    """The exact fixture from the original report, both orderings."""

    def test_credential_first_then_markdown_scheme(self, tmp_path: Path) -> None:
        codes = _urp_codes(tmp_path, f"{_CREDENTIAL}\n\n{_MD_SCHEME}")
        assert "Z205" in codes, f"Z205 dropped when a credential precedes it: {codes}"

    def test_markdown_scheme_first_then_credential(self, tmp_path: Path) -> None:
        """Order must not matter — a first hit must not consume the pass."""
        codes = _urp_codes(tmp_path, f"{_MD_SCHEME}\n\n{_CREDENTIAL}")
        assert "Z205" in codes, f"Z205 dropped when it precedes a credential: {codes}"

    def test_both_on_the_same_line(self, tmp_path: Path) -> None:
        codes = _urp_codes(tmp_path, f"See {_MD_SCHEME} and {_CREDENTIAL}")
        assert "Z205" in codes, f"Z205 dropped when sharing a line: {codes}"

    def test_html_scheme_alongside_a_credential(self, tmp_path: Path) -> None:
        codes = _urp_codes(tmp_path, f"{_CREDENTIAL}\n\n{_HTML_SCHEME}")
        assert "Z205" in codes, f"Z205 dropped in HTML form beside a credential: {codes}"


class TestMultipleSchemesInOneFile:
    """Two forbidden-scheme links in one file must both report."""

    def test_two_markdown_schemes_both_reported(self, tmp_path: Path) -> None:
        body = "[a](javascript:alert(1))\n\n[b](javascript:alert(2))"
        assert _urp_codes(tmp_path, body).count("Z205") == 2

    def test_markdown_and_html_scheme_both_reported(self, tmp_path: Path) -> None:
        body = f"{_MD_SCHEME}\n\n{_HTML_SCHEME}"
        assert _urp_codes(tmp_path, body).count("Z205") == 2

    def test_scheme_survives_two_credentials(self, tmp_path: Path) -> None:
        body = f"{_CREDENTIAL}\n{_SECOND_CREDENTIAL}\n\n{_MD_SCHEME}"
        assert "Z205" in _urp_codes(tmp_path, body)


class TestNoFalsePositives:
    """The guard must not turn into an over-reporter."""

    def test_credential_alone_emits_no_scheme_finding(self, tmp_path: Path) -> None:
        assert "Z205" not in _urp_codes(tmp_path, _CREDENTIAL)

    def test_ordinary_page_is_clean(self, tmp_path: Path) -> None:
        codes = _urp_codes(tmp_path, "[guide](guide.md)\n[site](https://example.com/x)")
        assert "Z205" not in codes
