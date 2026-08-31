# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Z205 (FORBIDDEN_SCHEME) must fire on Markdown links, not only HTML tags.

Z205 is a Tier-0, non-suppressible, Exit-2 gate. It was evaluated inside
``PolyglotExtractor._parse_node()``, reachable only from the HTML-tag scanning
loop, so a payload written in Markdown syntax passed the gate entirely:

    [click me](javascript:alert(document.cookie))   -> 0 findings, exit 0

while the identical payload as ``<a href="javascript:...">`` correctly produced
a security breach. The two forms are not equivalent in Zenzic but *are*
equivalent in the built site — a real ``mkdocs build`` of the Markdown form
emits ``<a href="javascript:alert(document.cookie)">click me</a>`` verbatim,
because Python-Markdown does not sanitise URI schemes.

The canonical gallery fixture contained only HTML elements, which is why every
existing test, the lab scenario and the gallery all exercised the covered half.
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core.adapters import get_adapter
from zenzic.core.incremental import IncrementalAnalysisEngine
from zenzic.core.scanner import _build_rule_engine
from zenzic.models.config import ZenzicConfig


def _findings(tmp_path: Path, text: str) -> list[str]:
    """Return the rule IDs the URP pass reports for *text*."""
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    page = docs / "index.md"
    page.write_text(text, encoding="utf-8")
    config = ZenzicConfig(docs_dir=Path("docs"))
    rule_engine = _build_rule_engine(config)
    engine = IncrementalAnalysisEngine(
        config=config,
        rule_engine=rule_engine,
        adapter=get_adapter(config.build_context, docs, tmp_path),
        docs_root=docs,
        repo_root=tmp_path,
    )
    return [f.rule_id for f in engine._run_urp_checks(None, page, text)]


class TestMarkdownInlineLinks:
    def test_javascript_scheme_in_markdown_link_is_caught(self, tmp_path: Path) -> None:
        """The exact payload from the discovery."""
        codes = _findings(tmp_path, "# T\n\n[click me](javascript:alert(document.cookie))\n")
        assert "Z205" in codes, (
            "a javascript: URI in Markdown link syntax passed the XSS gate; the "
            "same payload as an HTML <a href> is correctly caught"
        )

    def test_data_scheme_in_markdown_link_is_deliberately_not_flagged(
        self, tmp_path: Path
    ) -> None:
        """Scope decision, deliberate: the Markdown path checks javascript: only.

        Z205 is non-suppressible and exits 2, so a false positive hard-fails a
        build with no escape hatch. ``data:`` in Markdown is overwhelmingly
        benign (inline base64 images, ``data:text/plain``) and the pre-existing
        skip-scheme behaviour already treats it as such. ``data:`` remains
        flagged in HTML exactly as before. Narrowing dangerous ``data:``
        subtypes needs MIME discrimination and is tracked separately.
        """
        codes = _findings(tmp_path, "# T\n\n[x](data:text/plain,hello)\n")
        assert "Z205" not in codes


class TestMarkdownImages:
    def test_inline_base64_image_is_not_flagged(self, tmp_path: Path) -> None:
        """The false positive the narrowed scope exists to avoid: a legitimate
        inline image must not hard-fail a build through a gate that cannot be
        suppressed.
        """
        codes = _findings(
            tmp_path, "# T\n\n![logo](data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==)\n"
        )
        assert "Z205" not in codes

    def test_javascript_in_markdown_image_is_caught(self, tmp_path: Path) -> None:
        codes = _findings(tmp_path, "# T\n\n![x](javascript:alert(1))\n")
        assert "Z205" in codes


class TestReferenceDefinitions:
    def test_javascript_scheme_in_reference_definition_is_caught(self, tmp_path: Path) -> None:
        codes = _findings(tmp_path, "# T\n\n[click][ref]\n\n[ref]: javascript:alert(1)\n")
        assert "Z205" in codes


class TestNoRegression:
    def test_html_form_still_caught(self, tmp_path: Path) -> None:
        """The already-working half must keep working."""
        codes = _findings(tmp_path, '# T\n\n<a href="javascript:void(0)">x</a>\n')
        assert "Z205" in codes

    def test_ordinary_links_are_not_flagged(self, tmp_path: Path) -> None:
        """No false positives on the overwhelmingly common cases."""
        text = (
            "# T\n\n[rel](guide.md)\n[abs](https://example.com/x)\n"
            "[anchor](#section)\n[mail](mailto:a@example.com)\n![img](../assets/logo.png)\n"
        )
        assert "Z205" not in _findings(tmp_path, text)

    def test_no_duplicate_finding_for_the_same_html_node(self, tmp_path: Path) -> None:
        """The HTML node must be reported once, not once per extraction path."""
        codes = _findings(tmp_path, '# T\n\n<a href="javascript:void(0)">x</a>\n')
        assert codes.count("Z205") == 1, f"duplicated Z205 emission: {codes}"
