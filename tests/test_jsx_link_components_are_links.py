# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A capitalised tag with a URL-bearing attribute is a link.

The extension promises findings "in Markdown and MDX". A broken target in
``<Link to="./missing.md">`` was not reported, so the product claimed more than
it delivered -- which is the defect, independent of under-reporting being the
safer of two failures.

The rule is deliberately not a list of known component names. ``Link``,
``Anchor`` and ``Button`` are conventions, and any list of them is incomplete by
construction. What is recognised is the JSX convention itself: a lowercase tag is
an HTML element, a capitalised one is a component. That names no framework and
covers components nobody has thought of, which is what the last test here exists
to prove.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


CONFIG = 'docs_dir = "docs"\nfail_under = 0\n\n[build_context]\nengine = "standalone"\n'
PROSE = (
    "Padding prose so the word-count rule stays quiet and only the link under "
    "discussion decides what this page reports today."
)
ZENZIC = shutil.which("zenzic")

pytestmark = pytest.mark.skipif(ZENZIC is None, reason="needs the installed zenzic console script")


def _codes(tmp_path: Path, body: str) -> tuple[set[str], int]:
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / ".zenzic.toml").write_text(CONFIG, encoding="utf-8")
    (tmp_path / "docs" / "index.mdx").write_text(f"# T\n\n{body}\n\n{PROSE}\n", encoding="utf-8")
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env["COLUMNS"] = "200"
    proc = subprocess.run(  # noqa: S603
        [str(ZENZIC), "check", "references", "--no-header"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    out = proc.stdout + proc.stderr
    found = {c.strip("[]") for c in __import__("re").findall(r"\[Z\d{3}\]", out)}
    return found, proc.returncode


def _output(tmp_path: Path, body: str) -> tuple[str, int]:
    """Raw output plus exit code.

    A forbidden scheme is rendered as the security breach block, not as a
    bracketed `[Z205]` on a finding line, so a code-scraping assertion misses it
    for `<a href>` exactly as it does for a component. The exit code is the
    contract worth asserting.

    The block's ``Link:`` row currently shows the attribute *name* rather than the
    offending URL -- for `<a href>` as much as for a component, so it is not a
    consequence of component support. Logged separately; asserted here on the
    scheme, which is what the block does report.
    """
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / ".zenzic.toml").write_text(CONFIG, encoding="utf-8")
    (tmp_path / "docs" / "index.mdx").write_text(f"# T\n\n{body}\n\n{PROSE}\n", encoding="utf-8")
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    env["COLUMNS"] = "200"
    proc = subprocess.run(  # noqa: S603
        [str(ZENZIC), "check", "references", "--no-header"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    return proc.stdout + proc.stderr, proc.returncode


class TestABrokenTargetIsReported:
    def test_link_to_a_missing_page(self, tmp_path: Path) -> None:
        codes, _ = _codes(tmp_path, '<Link to="./nowhere.mdx">gone</Link>')
        assert "Z101" in codes, (
            f"<Link to> with a missing target produced no broken-link finding: {codes}"
        )

    def test_anchor_href_to_a_missing_page(self, tmp_path: Path) -> None:
        codes, _ = _codes(tmp_path, '<Anchor href="./nowhere.mdx">gone</Anchor>')
        assert "Z101" in codes, f"<Anchor href> was not analysed: {codes}"

    def test_a_component_nobody_has_named(self, tmp_path: Path) -> None:
        """The rule must be general, not a disguised list.

        If this passes only for Link/Anchor/Button, the implementation is a list
        wearing a regex and the next component invented is uncovered again.
        """
        codes, _ = _codes(tmp_path, '<QuuxWidget to="./nowhere.mdx">gone</QuuxWidget>')
        assert "Z101" in codes, (
            "an unnamed capitalised component was not analysed, so the rule is a "
            f"list of known names rather than the JSX convention: {codes}"
        )

    def test_self_closing_component(self, tmp_path: Path) -> None:
        codes, _ = _codes(tmp_path, '<Thumb src="./nowhere.png" />')
        assert "Z104" in codes or "Z101" in codes, f"self-closing form not analysed: {codes}"


class TestASecurityFindingStillFires:
    def test_the_control_form_is_caught(self, tmp_path: Path) -> None:
        """Positive control: `<a href>` must fail here, or the next two prove nothing."""
        out, rc = _output(tmp_path, '<a href="javascript:alert(1)">x</a>')
        assert rc == 2, f"the control did not reach the security tier: {rc}\n{out}"
        assert "forbidden scheme 'javascript:'" in out, f"the scheme was not named: {out}"

    def test_forbidden_scheme_in_a_component(self, tmp_path: Path) -> None:
        out, rc = _output(tmp_path, '<Link to="javascript:alert(1)">x</Link>')
        assert rc == 2, f"a forbidden scheme in a component did not exit 2: {rc}\n{out}"
        assert "forbidden scheme 'javascript:'" in out, f"the scheme was not named: {out}"

    def test_forbidden_scheme_in_an_unnamed_component(self, tmp_path: Path) -> None:
        out, rc = _output(tmp_path, '<QuuxWidget href="javascript:alert(1)">x</QuuxWidget>')
        assert rc == 2, f"not caught on an unnamed component: {rc}\n{out}"
        assert "forbidden scheme 'javascript:'" in out, out


class TestTheOtherDirection:
    """Silence where silence is correct -- without these the rule is untested."""

    def test_a_valid_component_link_is_silent(self, tmp_path: Path) -> None:
        codes, rc = _codes(tmp_path, '<Link to="./index.mdx">here</Link>')
        assert "Z101" not in codes, f"a valid target produced a broken-link finding: {codes}"
        assert rc == 0, f"expected a clean exit, got {rc}: {codes}"

    def test_a_non_url_prop_is_not_treated_as_a_link(self, tmp_path: Path) -> None:
        """A capitalised tag whose attributes carry no URL must stay silent.

        This is the false-positive guard: the rule keys on the three
        URL-bearing prop names, not on every string attribute a component takes.
        """
        codes, rc = _codes(tmp_path, '<Chart title="./nowhere.mdx" label="./also-nowhere.mdx" />')
        assert "Z101" not in codes, (
            f"a non-URL prop was resolved as a link target: {codes}. The rule must key "
            "on to/href/src, not on any attribute that happens to look like a path."
        )
        assert rc == 0, f"expected a clean exit, got {rc}: {codes}"

    def test_a_lowercase_unknown_tag_is_not_a_component(self, tmp_path: Path) -> None:
        """Lowercase is HTML, and an unknown HTML element is not a link."""
        codes, _ = _codes(tmp_path, '<mything to="./nowhere.mdx">x</mything>')
        assert "Z101" not in codes, f"a lowercase tag was treated as a JSX component: {codes}"
