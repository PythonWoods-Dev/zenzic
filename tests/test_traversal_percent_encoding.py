# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A traversal check that reads raw text cannot see an encoded traversal.

``incremental.py`` decided a link was worth examining with ``if "../" in url``
— a literal substring test against the URL exactly as written. ``%2f`` is the
same slash to everything that resolves the link and a different byte to that
test, so ``..%2f..%2fetc%2fpasswd`` reached the same file as
``../../etc/passwd`` while producing **no finding at all**: exit 0, on the one
code the Exit Code Contract declares non-suppressible.

Encoding the dots (``%2e%2e%2f``) hides it the same way. Double-encoding
(``..%252f``) hid it differently and worse — it survived as an ordinary
relative path, so the link checker reported ``Z101`` (broken link, exit 1) and
the security tier never ran, which reads as "we looked and it was fine."

The classifier is now given the decoded path, decoded repeatedly until it
stops changing, so the check and the resolver finally agree on what the URL
says. Decoding must not *invent* traversal: the boundary cases below pin that
an encoded link landing inside the docs root stays clean, and an encoded link
merely leaving it stays ``Z202``/exit 1 rather than being promoted to the
fatal tier.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.core.validator import _classify_traversal_intent
from zenzic.main import app


_PROSE = "Prose long enough to clear the minimum word-count check comfortably here."

#: Every spelling of ``../../../../etc/passwd`` that resolves to the same place.
_ENCODED_SYSTEM_TRAVERSALS = [
    pytest.param("../../../../etc/passwd", id="plain"),
    pytest.param("..%2f..%2f..%2f..%2fetc%2fpasswd", id="encoded-slash-lower"),
    pytest.param("..%2F..%2F..%2F..%2Fetc%2Fpasswd", id="encoded-slash-upper"),
    pytest.param("%2e%2e%2f%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd", id="encoded-dots"),
    pytest.param("..%252f..%252f..%252f..%252fetc%252fpasswd", id="double-encoded"),
    pytest.param("..%2f..%2F../%2e%2e/etc/passwd", id="mixed-spellings"),
]


def _run(tmp_path: Path, body: str, extra: list[str] | None = None) -> int:
    (tmp_path / "mkdocs.yml").write_text("site_name: Demo\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n', encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    for rel in extra or []:
        target = docs / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# T\n\n{_PROSE}\n", encoding="utf-8")
    (docs / "index.md").write_text(f"# P\n\n{_PROSE}\n\n{body}\n", encoding="utf-8")
    return (
        CliRunner()
        .invoke(app, ["check", "all", str(docs), "--no-header", "--quiet"], catch_exceptions=False)
        .exit_code
    )


class TestEncodingDoesNotHideASystemTraversal:
    @pytest.mark.parametrize("target", _ENCODED_SYSTEM_TRAVERSALS)
    def test_markdown_link_exits_3(self, tmp_path: Path, target: str) -> None:
        assert _run(tmp_path, f"[x]({target})") == 3, (
            f"'{target}' resolves to /etc/passwd and did not raise the non-suppressible Z203"
        )

    @pytest.mark.parametrize("target", _ENCODED_SYSTEM_TRAVERSALS)
    def test_html_href_exits_3(self, tmp_path: Path, target: str) -> None:
        assert _run(tmp_path, f'<a href="{target}">x</a>') == 3, (
            f"'{target}' escaped the Z203 gate when written as raw HTML"
        )

    def test_encoded_absolute_path_to_a_system_dir_exits_3(self, tmp_path: Path) -> None:
        """``%2fetc%2fpasswd`` is an absolute path wearing a disguise."""
        assert _run(tmp_path, "[x](%2fetc%2fpasswd)") == 3


class TestClassifierSeesThroughEncoding:
    @pytest.mark.parametrize(
        "href",
        [
            "..%2f..%2fetc%2fpasswd",
            "..%2F..%2FETC%2Fpasswd",
            "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252fetc%252fpasswd",
        ],
    )
    def test_encoded_system_targets_are_suspicious(self, href: str) -> None:
        assert _classify_traversal_intent(href) == "suspicious"

    @pytest.mark.parametrize(
        "href",
        [
            "..%2f..%2fsibling-repo%2fREADME.md",
            "%2e%2e%2fnotes%2fguide.md",
        ],
    )
    def test_encoded_non_system_targets_stay_boundary(self, href: str) -> None:
        """Decoding must reveal intent, not manufacture it."""
        assert _classify_traversal_intent(href) == "boundary"


class TestDecodingDoesNotInventTraversal:
    """The negative controls. A decoder that over-reaches is its own defect."""

    def test_encoded_space_in_a_real_filename_is_not_a_traversal(self, tmp_path: Path) -> None:
        assert _run(tmp_path, "[x](file%20name.md)", extra=["file name.md"]) != 3

    def test_encoded_subdirectory_link_is_not_a_traversal(self, tmp_path: Path) -> None:
        assert _run(tmp_path, "[x](guide%2fintro.md)", extra=["guide/intro.md"]) != 3

    def test_encoded_boundary_escape_stays_on_the_non_fatal_tier(self, tmp_path: Path) -> None:
        """Leaving the docs root is Z202/exit 1; only landing on a system root is exit 3."""
        assert _run(tmp_path, "[x](..%2f..%2fsibling-repo%2fREADME.md)") == 1

    def test_a_clean_page_stays_clean(self, tmp_path: Path) -> None:
        assert _run(tmp_path, "[x](guide.md)", extra=["guide.md"]) == 0
