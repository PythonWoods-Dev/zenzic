# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for Zenzic validator: link extraction, internal / external link validation, snippets."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from _helpers import make_mgr

from zenzic.core.validator import (
    _MAX_CONCURRENT_REQUESTS,
    PolyglotExtractor,
    _build_ref_map,
    _classify_traversal_intent,
    _find_cycles_iterative,
    anchors_in_file,
    extract_links,
    extract_ref_links,
    slug_heading,
    validate_links,
    validate_links_structured,
    validate_snippets,
)
from zenzic.models.config import ZenzicConfig


def _ul(links: list) -> list[tuple[str, int]]:  # type: ignore[type-arg]
    """Extract (url, lineno) pairs for easy assertion comparison."""
    return [(link.url, link.lineno) for link in links]


# ── extract_links (pure) ─────────────────────────────────────────────────────


class TestExtractLinks:
    """Pure extraction of (url, lineno) pairs from raw markdown text."""

    def test_simple_link(self) -> None:
        assert _ul(extract_links("[text](page.md)")) == [("page.md", 1)]

    def test_image_link(self) -> None:
        assert _ul(extract_links("![logo](assets/logo.png)")) == [("assets/logo.png", 1)]

    def test_link_with_title_stripped(self) -> None:
        assert _ul(extract_links('[click](page.md "My Page")')) == [("page.md", 1)]

    def test_link_with_single_quote_title_stripped(self) -> None:
        assert _ul(extract_links("[click](page.md 'My Page')")) == [("page.md", 1)]

    def test_empty_url_ignored(self) -> None:
        assert extract_links("[empty]()") == []

    def test_multiple_links_same_line(self) -> None:
        assert _ul(extract_links("[a](a.md) and [b](b.md)")) == [("a.md", 1), ("b.md", 1)]

    def test_correct_line_numbers(self) -> None:
        text = "line one\n[link](target.md)\nline three"
        assert _ul(extract_links(text)) == [("target.md", 2)]

    def test_link_inside_fenced_block_ignored(self) -> None:
        text = "```\n[fake](ghost.md)\n```"
        assert extract_links(text) == []

    def test_link_before_and_after_fenced_block_found(self) -> None:
        text = "[before](before.md)\n```\n[fake](ghost.md)\n```\n[after](after.md)"
        urls = [link.url for link in extract_links(text)]
        assert urls == ["before.md", "after.md"]
        assert "ghost.md" not in urls

    def test_link_inside_inline_code_ignored(self) -> None:
        assert extract_links("Use `[text](url)` syntax.") == []

    def test_link_mixed_inline_code_and_real(self) -> None:
        text = "Example: `[fake](nope.md)` but [real](page.md)."
        urls = [link.url for link in extract_links(text)]
        assert urls == ["page.md"]
        assert "nope.md" not in urls

    def test_link_with_fragment(self) -> None:
        assert _ul(extract_links("[sec](page.md#setup)")) == [("page.md#setup", 1)]

    def test_external_https_url(self) -> None:
        assert _ul(extract_links("[docs](https://example.com)")) == [("https://example.com", 1)]

    def test_reference_style_link_not_extracted(self) -> None:
        # [text][ref] is reference-style; not an inline link — must not be matched.
        assert extract_links("[text][ref]\n[ref]: page.md") == []

    @pytest.mark.parametrize(
        "content",
        [
            "~~~\n[fake](ghost.md)\n~~~",  # tilde fenced block
            "```python\n[fake](ghost.md)\n```",  # fenced block with language
        ],
    )
    def test_various_fence_styles_ignored(self, content: str) -> None:
        assert extract_links(content) == []


class TestPolyglotUnifiedExtractor:
    """Tests for PolyglotExtractor.extract_all_links and unified link extraction."""

    def test_extract_all_links_mixed_sources(self) -> None:
        doc = (
            "# Document Title\n"
            "\n"
            "Here is an [inline link](https://example.com/a.md).\n"
            '<a href="https://example.com/b.html">HTML link</a>\n'
            "\n"
            "![an image](assets/pic.png)\n"
            "\n"
            "[ref_alias]: https://example.com/c.md\n"
        )
        extractor = PolyglotExtractor()
        all_links = extractor.extract_all_links(doc)

        assert len(all_links) == 4

        # Verify links ordered deterministically by line number
        assert all_links[0].url == "https://example.com/a.md"
        assert all_links[0].line_no == 3
        assert all_links[0].is_html is False
        assert all_links[0].node_type == "inline"

        assert all_links[1].url == "https://example.com/b.html"
        assert all_links[1].line_no == 4
        assert all_links[1].is_html is True
        assert all_links[1].node_type == "html_a"

        assert all_links[2].url == "assets/pic.png"
        assert all_links[2].line_no == 6
        assert all_links[2].is_html is False
        assert all_links[2].node_type == "image"

        assert all_links[3].url == "https://example.com/c.md"
        assert all_links[3].line_no == 8
        assert all_links[3].is_html is False
        assert all_links[3].node_type == "ref_def"

    def test_extract_all_links_skips_code_fences(self) -> None:
        doc = (
            "```markdown\n"
            "[example](https://example.com/inside-fence.md)\n"
            '<a href="https://example.com/inside-html.html">inside</a>\n'
            "```\n"
            "[real](https://example.com/outside.md)\n"
        )
        extractor = PolyglotExtractor()
        all_links = extractor.extract_all_links(doc)

        assert len(all_links) == 1
        assert all_links[0].url == "https://example.com/outside.md"
        assert all_links[0].line_no == 5


class TestForbiddenSchemeBypassPrevention:
    """Z205 forbidden-scheme detection must survive 4 known bypass techniques.

    Regression coverage for a fixture (``tests/fixtures/z205-bypass-test.md``,
    from Direttiva CEO onwards) that documented these payloads but was never
    actually loaded by any test — the payloads themselves were confirmed still
    genuinely caught by live end-to-end reproduction before writing these
    (``zenzic check all --show-info`` on each, real ``SECURITY BREACH
    DETECTED`` panel, real Exit 2, for all 4). These tests assert the same
    detection at the unit level: ``HtmlNodeInfo.z205_scheme`` is the field
    ``_parse_node`` sets when ``_POLY_FORBIDDEN_SCHEMES`` matches the
    normalised href (``html.unescape`` then whitespace/control-char strip,
    applied before the scheme comparison — the exact mechanism that defeats
    all 4 techniques below).
    """

    def test_double_href_attack_uses_first_occurrence(self) -> None:
        """A second, decoy href must not shadow a malicious first href."""
        html = '<a href="javascript:alert(1)" href="safe.md">Double Href Attack</a>'
        nodes = PolyglotExtractor().extract(html)

        assert len(nodes) == 1
        assert nodes[0].href == "javascript:alert(1)"
        assert nodes[0].z205_scheme == "javascript:"

    def test_html_entity_encoded_scheme_is_unescaped_before_check(self) -> None:
        """A numeric HTML entity inside the scheme must not bypass detection."""
        html = '<a href="&#106;avascript:alert(1)">HTML Entities</a>'
        nodes = PolyglotExtractor().extract(html)

        assert len(nodes) == 1
        assert nodes[0].z205_scheme == "javascript:"

    def test_embedded_whitespace_in_scheme_is_stripped_before_check(self) -> None:
        """A literal space inside the scheme must not bypass detection."""
        html = '<a href="java script:alert(1)">Whitespace</a>'
        nodes = PolyglotExtractor().extract(html)

        assert len(nodes) == 1
        assert nodes[0].z205_scheme == "javascript:"

    def test_embedded_control_char_in_scheme_is_stripped_before_check(self) -> None:
        """An HTML-entity-encoded control character must not bypass detection."""
        html = '<a href="java&#x09;script:alert(1)">Control Chars</a>'
        nodes = PolyglotExtractor().extract(html)

        assert len(nodes) == 1
        assert nodes[0].z205_scheme == "javascript:"


# ─── slug_heading (pure) ──────────────────────────────────────────────────────


class TestSlugHeading:
    """Heading text → URL-safe anchor slug."""

    @pytest.mark.parametrize(
        "heading, expected",
        [
            ("Hello World", "hello-world"),
            ("Quick-Start Guide!", "quick-start-guide"),
            ("foo-bar", "foo-bar"),
            ("  foo   bar  ", "foo-bar"),
            ("API Reference (v2)", "api-reference-v2"),
            ('Install with uv { data-toc-label="with uv" }', "install-with-uv"),
            ("Caret, Mark & Tilde { #caret-mark-tilde }", "caret-mark-tilde"),
            ("", ""),
        ],
    )
    def test_slug(self, heading: str, expected: str) -> None:
        assert slug_heading(heading) == expected


# ─── anchors_in_file (pure) ───────────────────────────────────────────────────


class TestAnchorsInFile:
    """Extract anchor slug set from raw markdown content."""

    def test_single_heading(self) -> None:
        assert anchors_in_file("# Introduction\n") == {"introduction"}

    def test_multiple_heading_levels(self) -> None:
        content = "# Top\n## Sub\n### Deep\n"
        assert anchors_in_file(content) == {"top", "sub", "deep"}

    def test_mixed_content(self) -> None:
        content = "# Quick Start\n\nSome text.\n\n## Installation\n"
        assert anchors_in_file(content) == {"quick-start", "installation"}

    def test_no_headings(self) -> None:
        assert anchors_in_file("Just plain text.") == set()

    def test_heading_with_special_chars(self) -> None:
        assert "api-reference-v2" in anchors_in_file("## API Reference (v2)\n")

    def test_explicit_anchors_and_footnotes(self) -> None:
        content = (
            "# Heading\n"
            "This is a paragraph with an anchor { #custom-id }.\n"
            "&nbsp;\n"
            '{ #feedback style="color: red" }\n'
            "[^1]: This is a footnote definition.\n"
            "```\n"
            "Ignore this { #ignored-inside-code-block }\n"
            "```\n"
        )
        assert anchors_in_file(content) == {"heading", "custom-id", "feedback", "fn:1"}

    def test_html_inline_id_anchors(self) -> None:
        content = (
            "Here is <a id='my-anchor'>a link</a> and <span id=\"another-anchor\">span</span>.\n"
            "Inside code: `not <a id='ignored'>`.\n"
            "```\n"
            "<div id='code-block-ignored'>\n"
            "```\n"
        )
        assert anchors_in_file(content) == {"my-anchor", "another-anchor"}


# ─── Internal link validation ─────────────────────────────────────────────────


class TestInternalLinks:
    """validate_links with strict=False (default) — no network, filesystem only."""

    def test_valid_link(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[setup](setup.md)")
        (docs / "setup.md").write_text("# Setup\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []

    def test_missing_target_file(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[ghost](ghost.md)")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        assert len(errors) == 1
        assert "ghost.md" in errors[0]

    def test_valid_anchor(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[section](guide.md#installation)")
        (docs / "guide.md").write_text("# Guide\n\n## Installation\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []

    def test_invalid_anchor(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[broken](guide.md#nonexistent)")
        (docs / "guide.md").write_text("# Guide\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        assert len(errors) == 1
        assert "nonexistent" in errors[0]

    def test_link_in_fenced_block_ignored(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("```\n[fake](ghost.md)\n```\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []

    def test_path_traversal_rejected(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[escape](../../etc/passwd)")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        assert len(errors) == 1
        assert "outside" in errors[0]

    def test_extension_less_link_resolves(self, tmp_path: Path) -> None:
        """MkDocs pretty URLs: [setup](setup) should resolve to setup.md."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[setup](setup)")
        (docs / "setup.md").write_text("# Setup\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []

    def test_directory_index_link_resolves(self, tmp_path: Path) -> None:
        """[section](section/) should resolve to section/index.md."""
        docs = tmp_path / "docs"
        docs.mkdir()
        section = docs / "section"
        section.mkdir()
        (section / "index.md").write_text("# Section\n")
        (docs / "index.md").write_text("[section](section/)")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []

    def test_non_markdown_asset_missing_reported(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[dl](files/report.pdf)")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        assert len(errors) == 1
        assert "report.pdf" in errors[0]

    def test_non_markdown_asset_exists_ok(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "files").mkdir()
        (docs / "files" / "report.pdf").write_bytes(b"%PDF")
        (docs / "index.md").write_text("[dl](files/report.pdf)")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []

    def test_skip_schemes_ignored(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text(
            "[mail](mailto:dev@example.com)\n[data](data:text/plain,hello)\n"
        )
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []

    def test_docs_dir_missing_returns_empty(self, tmp_path: Path) -> None:
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []

    def test_symlinks_skipped(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        real = outside / "real.md"
        real.write_text("[broken](ghost.md)")
        (docs / "linked.md").symlink_to(real)
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=docs)
        assert validate_links(docs_root, mgr, repo_root=docs, config=config) == []

    def test_excluded_dir_not_scanned(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        overrides = docs / "overrides"
        overrides.mkdir()
        (overrides / "page.md").write_text("[broken](ghost.md)")
        (tmp_path / ".zenzic.toml").write_text('excluded_dirs = ["overrides"]\n')
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []

    def test_errors_are_sorted(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("[z](zzz.md)")
        (docs / "b.md").write_text("[a](aaa.md)")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        assert errors == sorted(errors)

    @pytest.mark.slow
    def test_anchor_torture_parallel_indexing_1000_files(self, tmp_path: Path) -> None:
        """1000 cross-linked anchors must validate without race-induced false positives.

        Windows uses spawn (not fork) — scale down to 100 files to stay within
        the 120s pytest-timeout budget on GitHub Actions Windows runners.
        """
        import os

        docs = tmp_path / "docs"
        docs.mkdir()

        total = 100 if os.name == "nt" else 1000
        for i in range(total):
            nxt = i + 1
            # Linear chain: each page links to the next (no ring to avoid CIRCULAR_LINK).
            # The last page has no forward link — it is the terminal node.
            if nxt < total:
                link_line = f"Forward link: [next](page_{nxt:04d}.md#section-{nxt})"
            else:
                link_line = "Terminal node — no forward link."
            (docs / f"page_{i:04d}.md").write_text(
                "\n".join(
                    [
                        f"# Page {i}",
                        f"## Section {i}",
                        "",
                        link_line,
                        "",
                        "This page is part of the anchor torture fixture and remains deterministic.",
                    ]
                ),
                encoding="utf-8",
            )

        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []


# ─── Path-traversal intent classification ─────────────────────────────────────


class TestTraversalIntent:
    """_classify_traversal_intent separates boundary from suspicious traversals."""

    def test_system_paths_are_suspicious(self) -> None:
        assert _classify_traversal_intent("../../../../etc/passwd") == "suspicious"
        assert _classify_traversal_intent("../../root/.ssh/id_rsa") == "suspicious"
        assert _classify_traversal_intent("../../../var/log/syslog") == "suspicious"
        assert _classify_traversal_intent("../../../proc/self/mem") == "suspicious"
        assert _classify_traversal_intent("../../../../usr/bin/env") == "suspicious"

    def test_boundary_traversal_not_suspicious(self) -> None:
        assert _classify_traversal_intent("../../outside.md") == "boundary"
        assert _classify_traversal_intent("../sibling.md") == "boundary"
        assert _classify_traversal_intent("../../README.md") == "boundary"

    def test_path_traversal_suspicious_error_type(self, tmp_path: Path) -> None:
        """validate_links_structured emits PATH_TRAVERSAL_SUSPICIOUS for OS system dirs."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[escape](../../../../etc/passwd)")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links_structured(docs_root, mgr, repo_root=tmp_path, config=config)
        assert len(errors) == 1
        assert errors[0].error_type == "Z203"

    def test_path_traversal_boundary_error_type(self, tmp_path: Path) -> None:
        """validate_links_structured emits PATH_TRAVERSAL for non-system out-of-bounds hrefs."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[escape](../../outside.md)")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links_structured(docs_root, mgr, repo_root=tmp_path, config=config)
        assert len(errors) == 1
        assert errors[0].error_type == "Z202"


# ─── Absolute-path prohibition ───────────────────────────────────────────────


class TestAbsolutePathProhibition:
    """Absolute internal links (starting with /) must be rejected."""

    def test_absolute_link_is_error(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[logo](/assets/logo.png)\n")
        (docs / "assets").mkdir()
        (docs / "assets" / "logo.png").write_bytes(b"")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        assert len(errors) == 1
        assert "/assets/logo.png" in errors[0]
        assert "absolute path" in errors[0]

    def test_absolute_link_to_md_is_error(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[guide](/guide.md)\n")
        (docs / "guide.md").write_text("# Guide\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        assert len(errors) == 1
        assert "absolute path" in errors[0]

    def test_relative_link_not_affected(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[guide](guide.md)\n")
        (docs / "guide.md").write_text("# Guide\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []

    def test_external_https_not_affected(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[ext](https://example.com)\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:8080/api",
            "http://localhost/path",
            "https://localhost:443/secure",
            "http://127.0.0.1:5000",
            "http://0.0.0.0:8000",
            "http://::1:3000",
        ],
    )
    def test_loopback_url_not_treated_as_external(self, tmp_path: Path, url: str) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text(f"[svc]({url})\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []

    def test_absolute_path_with_anchor_is_error(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[section](/guide.md#intro)\n")
        (docs / "guide.md").write_text("# Intro\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        assert len(errors) == 1
        assert "absolute path" in errors[0]

    def test_z105_fires_even_when_target_file_exists_on_disk(self, tmp_path: Path) -> None:
        """CEO-053 regression: Z105 is a hard pre-resolution gate.

        Even when the target file exists on disk, an absolute link must be
        flagged as ABSOLUTE_PATH (Z105) — the validator must never short-circuit
        the check because the file happens to be reachable locally.

        This test creates a real file, then links to it via an absolute path.
        The error_type must be ABSOLUTE_PATH, not FILE_NOT_FOUND.
        """
        docs = tmp_path / "docs"
        (docs / "assets").mkdir(parents=True)
        # Physical file exists — the link target is reachable on disk
        (docs / "assets" / "logo.png").write_bytes(b"\x89PNG")
        (docs / "index.md").write_text("![logo](/assets/logo.png)\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links_structured(docs_root, mgr, repo_root=tmp_path, config=config)
        assert len(errors) == 1
        assert errors[0].error_type == "Z105"


# ─── S4-2: known_assets pre-map + excluded_build_artifacts ───────────────────


class TestAssetPreMap:
    """Verify that asset validation is entirely in-memory after Pass 1.

    The key invariant: once known_assets is built in Pass 1, no Path.exists()
    call must occur inside the Pass 2 link-resolution loop.
    """

    def test_existing_asset_link_is_valid(self, tmp_path: Path) -> None:
        """A link to a non-.md file that exists in docs/ produces no error."""
        docs = tmp_path / "docs"
        (docs / "assets").mkdir(parents=True)
        (docs / "assets" / "logo.png").write_bytes(b"\x89PNG")
        (docs / "index.md").write_text("![logo](assets/logo.png)")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []

    def test_missing_asset_link_is_reported(self, tmp_path: Path) -> None:
        """A link to a non-.md file that does NOT exist in docs/ is an error."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[dl](files/report.pdf)")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        assert len(errors) == 1
        assert "report.pdf" in errors[0]

    def test_excluded_build_artifact_not_reported(self, tmp_path: Path) -> None:
        """Links to build-time generated assets (matching excluded_build_artifacts) are suppressed."""
        docs = tmp_path / "docs"
        (docs / "pdf").mkdir(parents=True)
        # pdf/document.pdf does NOT exist — generated by to-pdf at build time
        (docs / "index.md").write_text("[PDF](pdf/document.pdf)")
        (tmp_path / ".zenzic.toml").write_text('excluded_build_artifacts = ["pdf/*.pdf"]\n')
        config, _ = ZenzicConfig.load(tmp_path)
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []

    def test_excluded_build_artifact_does_not_suppress_other_missing(self, tmp_path: Path) -> None:
        """excluded_build_artifacts patterns are scoped — non-matching missing assets still error."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[PDF](pdf/document.pdf)\n[broken](other/file.zip)")
        (tmp_path / ".zenzic.toml").write_text('excluded_build_artifacts = ["pdf/*.pdf"]\n')
        config, _ = ZenzicConfig.load(tmp_path)
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        assert len(errors) == 1
        assert "file.zip" in errors[0]

    def test_absolute_asset_link_is_prohibited(self, tmp_path: Path) -> None:
        """Site-absolute asset links (/assets/logo.png) are now prohibited.

        Absolute paths break portability when the site is hosted in a
        subdirectory. The Absolute Link Prohibition rule catches them before
        any asset lookup, so the file existence is irrelevant.
        """
        docs = tmp_path / "docs"
        (docs / "assets").mkdir(parents=True)
        (docs / "assets" / "logo.png").write_bytes(b"\x89PNG")
        (docs / "index.md").write_text("![logo](/assets/logo.png)")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        assert len(errors) == 1
        assert "absolute path" in errors[0]

    def test_asset_case_sensitivity_linux(self, tmp_path: Path) -> None:
        """known_assets lookup is case-sensitive (Standard Unix/Web behaviour).

        Zenzic targets correctness on the canonical web platform (Linux/POSIX).
        ``documento.pdf`` and ``Documento.pdf`` are distinct files — a link to
        the wrong casing must be reported as a missing asset.

        Policy: Zenzic is case-sensitive by default.  Authors must use the
        exact case as on disk.  This matches the behaviour of web servers
        serving static files on Linux and avoids silent breakage when deploying
        a site built on macOS (case-insensitive HFS+) to a Linux host.
        """
        docs = tmp_path / "docs"
        (docs / "assets").mkdir(parents=True)
        # Only the lowercase file exists on disk
        (docs / "assets" / "documento.pdf").write_bytes(b"%PDF")
        (docs / "index.md").write_text("[PDF](assets/Documento.pdf)")  # wrong case
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        # On Linux (case-sensitive FS) the wrong-case link must be reported.
        # This test is authoritative on Linux CI; on macOS it may pass silently
        # due to HFS+ case-folding — that is a known platform divergence.
        import sys

        if sys.platform.startswith("linux"):
            assert len(errors) == 1
            assert "Documento.pdf" in errors[0]

    def test_no_path_exists_called_in_pass2(self, tmp_path: Path) -> None:
        """Path.exists() must not be called during Pass 2 (hot path is I/O-free)."""
        docs = tmp_path / "docs"
        (docs / "pdf").mkdir(parents=True)
        (docs / "pdf" / "real.pdf").write_bytes(b"%PDF")
        (docs / "index.md").write_text("[dl](pdf/real.pdf)")

        call_log: list[str] = []

        original_exists = Path.exists

        def spy_exists(self: Path) -> bool:
            call_log.append(str(self))
            return original_exists(self)

        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        with patch.object(Path, "exists", spy_exists):
            errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)

        assert errors == []
        # Pass 1 I/O is permitted (docs_root.is_dir(), rglob traversal calls exist internally).
        # The critical assertion: the resolved PDF path must NOT appear in call_log —
        # it must be found in known_assets without a disk call.
        pdf_str = str((docs / "pdf" / "real.pdf").resolve())
        assert pdf_str not in call_log, (
            f"Path.exists() was called for {pdf_str} — asset check is not in-memory!"
        )


# ─── S4-3: i18n fallback_to_default ─────────────────────────────────────────


def _mkdocs_i18n_folder(fallback: bool = True) -> str:
    """Return a minimal mkdocs.yml snippet with folder-mode i18n."""
    fallback_str = "true" if fallback else "false"
    return (
        "site_name: Test\n"
        "plugins:\n"
        "  - i18n:\n"
        "      docs_structure: folder\n"
        f"      fallback_to_default: {fallback_str}\n"
        "      languages:\n"
        "        - locale: en\n"
        "          default: true\n"
        "          build: true\n"
        "        - locale: it\n"
        "          build: true\n"
    )


class TestI18nFallbackIntegration:
    """Integration tests: validate_links with i18n fallback semantics."""

    def _setup(self, tmp_path: Path, *, fallback: bool = True) -> tuple[Path, Path, Path]:
        """Create a minimal folder-mode i18n repo. Returns (repo, docs, docs_it)."""
        docs = tmp_path / "docs"
        docs_it = docs / "it"
        docs_it.mkdir(parents=True)
        (tmp_path / "mkdocs.yml").write_text(_mkdocs_i18n_folder(fallback=fallback))
        return tmp_path, docs, docs_it

    def test_fallback_suppresses_untranslated_md_link(self, tmp_path: Path) -> None:
        """Link from it/ to an untranslated page is suppressed when fallback is on.

        docs/it/guide.md links to api.md (intra-locale).  The resolver looks for
        docs/it/api.md — which does not exist — producing FileNotFound.  Fallback
        then checks docs/api.md (default locale), finds it, and suppresses the error.
        """
        repo, docs, docs_it = self._setup(tmp_path)
        # Default-locale file exists; translated equivalent is absent.
        (docs / "api.md").write_text("# API\n")
        (docs_it / "guide.md").write_text("[api](api.md)\n")
        config = ZenzicConfig()
        docs_root = repo / config.docs_dir
        mgr = make_mgr(config, repo_root=repo)
        assert validate_links(docs_root, mgr, repo_root=repo, config=config) == []

    def test_no_fallback_reports_untranslated_md_link(self, tmp_path: Path) -> None:
        """Same intra-locale link is reported when fallback_to_default is false."""
        repo, docs, docs_it = self._setup(tmp_path, fallback=False)
        (docs / "api.md").write_text("# API\n")
        (docs_it / "guide.md").write_text("[api](api.md)\n")
        config = ZenzicConfig()
        docs_root = repo / config.docs_dir
        mgr = make_mgr(config, repo_root=repo)
        errors = validate_links(docs_root, mgr, repo_root=repo, config=config)
        assert len(errors) == 1
        assert "api.md" in errors[0]

    def test_fallback_reports_link_missing_in_both_locales(self, tmp_path: Path) -> None:
        """A page missing in BOTH locales is always reported as broken."""
        repo, docs, docs_it = self._setup(tmp_path)
        # ghost.md absent from both docs/ and docs/it/ — fallback cannot rescue it.
        (docs_it / "guide.md").write_text("[ghost](ghost.md)\n")
        config = ZenzicConfig()
        docs_root = repo / config.docs_dir
        mgr = make_mgr(config, repo_root=repo)
        errors = validate_links(docs_root, mgr, repo_root=repo, config=config)
        assert any("ghost" in e for e in errors)

    def test_fallback_suppresses_asset_missing_in_locale(self, tmp_path: Path) -> None:
        """Asset missing in it/ but present in default locale is suppressed by fallback."""
        repo, docs, docs_it = self._setup(tmp_path)
        (docs / "assets").mkdir()
        (docs / "assets" / "logo.png").write_bytes(b"\x89PNG")
        # docs/it/assets/logo.png absent — intra-locale relative link triggers FileNotFound.
        # Fallback maps docs/it/assets/logo.png → docs/assets/logo.png (in known_assets).
        (docs_it / "guide.md").write_text("![logo](assets/logo.png)\n")
        config = ZenzicConfig()
        docs_root = repo / config.docs_dir
        mgr = make_mgr(config, repo_root=repo)
        assert validate_links(docs_root, mgr, repo_root=repo, config=config) == []

    def test_direct_cross_locale_link_resolves_without_warning(self, tmp_path: Path) -> None:
        """A link from it/ that navigates directly to an EN file is Resolved (not FileNotFound).

        ../guide.md from docs/it/index.md normalises to docs/guide.md which exists
        directly — Resolved, no fallback logic involved.
        """
        repo, docs, docs_it = self._setup(tmp_path)
        (docs / "guide.md").write_text("# EN Guide\n")
        (docs_it / "index.md").write_text("[EN guide](../guide.md)\n")
        config = ZenzicConfig()
        docs_root = repo / config.docs_dir
        mgr = make_mgr(config, repo_root=repo)
        assert validate_links(docs_root, mgr, repo_root=repo, config=config) == []

    def test_config_error_no_default_locale(self, tmp_path: Path) -> None:
        """ConfigurationError when fallback=true but no default locale is declared."""
        from zenzic.core.exceptions import ConfigurationError

        docs = tmp_path / "docs"
        (docs / "it").mkdir(parents=True)
        bad_config = (
            "plugins:\n  - i18n:\n      docs_structure: folder\n"
            "      fallback_to_default: true\n"
            "      languages:\n        - locale: en\n        - locale: it\n"
        )
        (tmp_path / "mkdocs.yml").write_text(bad_config)
        (docs / "index.md").touch()
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        with pytest.raises(ConfigurationError):
            validate_links(docs_root, mgr, repo_root=tmp_path, config=config)

    # ── Anchor i18n fallback tests ─────────────────────────────────────────────

    def test_anchor_fallback_suppresses_translated_heading_miss(self, tmp_path: Path) -> None:
        """Anchor present in EN file but absent in IT file is suppressed by fallback.

        Scenario: docs/it/guide.md links to architecture.md#quick-start.
        The resolver normalises the target to docs/it/architecture.md (exists).
        docs/it/architecture.md uses translated headings, so "quick-start" is
        absent from its anchor set — AnchorMissing is produced.
        Fallback checks docs/architecture.md, finds "quick-start", and suppresses.
        """
        repo, docs, docs_it = self._setup(tmp_path)
        # EN file has the target anchor; IT file has a translated heading.
        (docs / "architecture.md").write_text("# Architecture\n\n## Quick Start\n")
        (docs_it / "architecture.md").write_text("# Architettura\n\n## Avvio Rapido\n")
        (docs_it / "guide.md").write_text("[qs](architecture.md#quick-start)\n")
        config = ZenzicConfig()
        docs_root = repo / config.docs_dir
        mgr = make_mgr(config, repo_root=repo)
        assert validate_links(docs_root, mgr, repo_root=repo, config=config) == []

    def test_anchor_fallback_reports_when_anchor_missing_in_both_locales(
        self, tmp_path: Path
    ) -> None:
        """An anchor absent in BOTH the IT and EN files is always reported.

        Fallback can only suppress the error when the EN file contains the anchor.
        If neither locale has it, the link is genuinely broken.
        """
        repo, docs, docs_it = self._setup(tmp_path)
        (docs / "architecture.md").write_text("# Architecture\n\n## Overview\n")
        (docs_it / "architecture.md").write_text("# Architettura\n\n## Panoramica\n")
        # "ghost-anchor" exists in neither EN nor IT file.
        (docs_it / "guide.md").write_text("[x](architecture.md#ghost-anchor)\n")
        config = ZenzicConfig()
        docs_root = repo / config.docs_dir
        mgr = make_mgr(config, repo_root=repo)
        errors = validate_links(docs_root, mgr, repo_root=repo, config=config)
        assert any("ghost-anchor" in e for e in errors)

    def test_anchor_fallback_disabled_reports_translated_heading_miss(self, tmp_path: Path) -> None:
        """When fallback_to_default is false, translated-heading misses are reported."""
        repo, docs, docs_it = self._setup(tmp_path, fallback=False)
        (docs / "architecture.md").write_text("# Architecture\n\n## Quick Start\n")
        (docs_it / "architecture.md").write_text("# Architettura\n\n## Avvio Rapido\n")
        (docs_it / "guide.md").write_text("[qs](architecture.md#quick-start)\n")
        config = ZenzicConfig()
        docs_root = repo / config.docs_dir
        mgr = make_mgr(config, repo_root=repo)
        errors = validate_links(docs_root, mgr, repo_root=repo, config=config)
        assert any("quick-start" in e for e in errors)

    def test_anchor_fallback_not_triggered_for_en_file_anchor_miss(self, tmp_path: Path) -> None:
        """A broken anchor in a default-locale (EN) file is always reported.

        Fallback suppression only applies when the source file is inside a
        non-default locale directory.  A link from docs/guide.md to
        docs/page.md#ghost must still be reported even with fallback enabled.
        """
        repo, docs, docs_it = self._setup(tmp_path)
        (docs / "page.md").write_text("# Page\n\n## Real Heading\n")
        (docs / "guide.md").write_text("[x](page.md#ghost-anchor)\n")
        config = ZenzicConfig()
        docs_root = repo / config.docs_dir
        mgr = make_mgr(config, repo_root=repo)
        errors = validate_links(docs_root, mgr, repo_root=repo, config=config)
        assert any("ghost-anchor" in e for e in errors)

    def test_anchor_in_it_file_resolves_directly_without_fallback(self, tmp_path: Path) -> None:
        """An anchor that exists in the IT file itself resolves without touching fallback."""
        repo, docs, docs_it = self._setup(tmp_path)
        (docs_it / "architecture.md").write_text("# Architettura\n\n## Avvio Rapido\n")
        (docs_it / "guide.md").write_text("[ar](architecture.md#avvio-rapido)\n")
        config = ZenzicConfig()
        docs_root = repo / config.docs_dir
        mgr = make_mgr(config, repo_root=repo)
        assert validate_links(docs_root, mgr, repo_root=repo, config=config) == []


# ─── S4-4: Reference-style link resolution ───────────────────────────────────


class TestBuildRefMap:
    """Unit tests for _build_ref_map (pure function)."""

    def test_basic_definition(self) -> None:
        assert _build_ref_map("[guide]: guide.md\n") == {"guide": "guide.md"}

    def test_case_insensitive_id(self) -> None:
        """CommonMark §4.7: reference IDs are case-insensitive."""
        result = _build_ref_map("[Guide]: guide.md\n[INSTALL]: install.md\n")
        assert result == {"guide": "guide.md", "install": "install.md"}

    def test_first_definition_wins(self) -> None:
        text = "[ref]: first.md\n[ref]: second.md\n"
        assert _build_ref_map(text) == {"ref": "first.md"}

    def test_skips_code_block(self) -> None:
        text = "```\n[in-block]: ghost.md\n```\n[real]: real.md\n"
        assert _build_ref_map(text) == {"real": "real.md"}

    def test_external_url_preserved(self) -> None:
        assert _build_ref_map("[ext]: https://example.com\n") == {"ext": "https://example.com"}

    def test_empty_content(self) -> None:
        assert _build_ref_map("") == {}

    def test_no_definitions(self) -> None:
        assert _build_ref_map("Just [some](inline.md) text.\n") == {}


class TestExtractRefLinks:
    """Unit tests for extract_ref_links (pure function)."""

    def test_simple_ref_link(self) -> None:
        text = "[guide][ref]\n[ref]: guide.md\n"
        ref_map = _build_ref_map(text)
        assert _ul(extract_ref_links(text, ref_map)) == [("guide.md", 1)]

    def test_collapsed_ref_link(self) -> None:
        text = "[guide][]\n[guide]: guide.md\n"
        ref_map = _build_ref_map(text)
        links = [link.url for link in extract_ref_links(text, ref_map)]
        assert "guide.md" in links

    def test_undefined_id_not_returned(self) -> None:
        text = "[ghost][undefined]\n"
        assert extract_ref_links(text, {}) == []

    def test_case_insensitive_lookup(self) -> None:
        ref_map = {"guide": "guide.md"}
        text = "[text][GUIDE]\n"
        links = [link.url for link in extract_ref_links(text, ref_map)]
        assert "guide.md" in links

    def test_skips_fenced_block(self) -> None:
        text = "```\n[fake][ref]\n```\n[real][ref]\n"
        ref_map = {"ref": "target.md"}
        links = extract_ref_links(text, ref_map)
        assert len(links) == 1
        assert links[0].lineno == 4  # line 4 (outside block)

    def test_skips_inline_code(self) -> None:
        text = "Use `[fake][ref]` syntax. [real][ref]\n"
        ref_map = {"ref": "target.md"}
        links = extract_ref_links(text, ref_map)
        assert len(links) == 1


class TestRefLinkValidation:
    """Integration: validate_links resolves reference-style links as internal links."""

    def test_ref_link_to_existing_md(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[guide][ref]\n\n[ref]: guide.md\n")
        (docs / "guide.md").write_text("# Guide\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []

    def test_ref_link_to_missing_md_reported(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[ghost][ref]\n\n[ref]: ghost.md\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config)
        assert any("ghost.md" in e for e in errors)

    def test_ref_link_external_url_checked_in_strict(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[ext][ref]\n\n[ref]: https://example.com\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        with patch("zenzic.core.validator._ping_url", new=AsyncMock(return_value=None)):
            errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config, strict=True)
        assert errors == []

    def test_ref_link_case_insensitive_id(self, tmp_path: Path) -> None:
        """[text][ID] must resolve the same as [text][id]."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[guide][GUIDE]\n\n[guide]: guide.md\n")
        (docs / "guide.md").write_text("# Guide\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []

    def test_ref_link_with_anchor(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[sec][ref]\n\n[ref]: guide.md#installation\n")
        (docs / "guide.md").write_text("# Guide\n## Installation\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        assert validate_links(docs_root, mgr, repo_root=tmp_path, config=config) == []


class TestEmptyLinkTextValidation:
    """Integration: empty link labels are reported as Z108."""

    def test_empty_inline_link_text_emits_z108(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[](guide.md)\n\n# Home\n")
        (docs / "guide.md").write_text("# Guide\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links_structured(docs_root, mgr, repo_root=tmp_path, config=config)
        z108 = [e for e in errors if e.error_type == "Z108"]
        assert len(z108) == 1

    def test_empty_reference_link_text_emits_z108(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[][guide]\n\n[guide]: guide.md\n")
        (docs / "guide.md").write_text("# Guide\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links_structured(docs_root, mgr, repo_root=tmp_path, config=config)
        z108 = [e for e in errors if e.error_type == "Z108"]
        assert len(z108) == 1


# ─── External link validation (httpx mocked via _ping_url) ───────────────────


class TestExternalLinks:
    """External link checks require strict=True.

    ``_ping_url`` is patched at module level so no real HTTP requests are made.
    The httpx.AsyncClient is still constructed but never used to send traffic.
    """

    def _setup_docs(self, tmp_path: Path, content: str) -> None:
        docs = tmp_path / "docs"
        docs.mkdir(exist_ok=True)
        (docs / "index.md").write_text(content)

    def test_strict_false_never_pings_external(self, tmp_path: Path) -> None:
        """With strict=False, _ping_url must never be invoked."""
        self._setup_docs(tmp_path, "[link](https://example.com/404)")
        mock_ping = AsyncMock(return_value=None)
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        with patch("zenzic.core.validator._ping_url", new=mock_ping):
            errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config, strict=False)
        mock_ping.assert_not_called()
        assert errors == []

    def test_http_200_no_error(self, tmp_path: Path) -> None:
        self._setup_docs(tmp_path, "[link](https://example.com)")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        with patch("zenzic.core.validator._ping_url", new=AsyncMock(return_value=None)):
            errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config, strict=True)
        assert errors == []

    def test_http_404_reported(self, tmp_path: Path) -> None:
        url = "https://example.com/missing"
        self._setup_docs(tmp_path, f"[broken]({url})")
        err_msg = f"external link '{url}' returned HTTP 404"
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        with patch("zenzic.core.validator._ping_url", new=AsyncMock(return_value=err_msg)):
            errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config, strict=True)
        assert len(errors) == 1
        assert "404" in errors[0]

    def test_http_403_treated_as_alive(self, tmp_path: Path) -> None:
        """403 is returned by _ping_url as None (no error) — servers restricting bots."""
        self._setup_docs(tmp_path, "[link](https://github.com)")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        with patch("zenzic.core.validator._ping_url", new=AsyncMock(return_value=None)):
            errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config, strict=True)
        assert errors == []

    def test_timeout_reported(self, tmp_path: Path) -> None:
        url = "https://slow.example.com"
        self._setup_docs(tmp_path, f"[slow]({url})")
        err_msg = f"external link '{url}' timed out (>10 s)"
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        with patch("zenzic.core.validator._ping_url", new=AsyncMock(return_value=err_msg)):
            errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config, strict=True)
        assert len(errors) == 1
        assert "timed out" in errors[0]

    def test_connection_error_reported(self, tmp_path: Path) -> None:
        url = "https://unreachable.invalid"
        self._setup_docs(tmp_path, f"[dead]({url})")
        err_msg = f"external link '{url}' — connection error: [Errno -2] Name or service not known"
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        with patch("zenzic.core.validator._ping_url", new=AsyncMock(return_value=err_msg)):
            errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config, strict=True)
        assert len(errors) == 1
        assert "connection error" in errors[0]

    def test_duplicate_url_pinged_exactly_once(self, tmp_path: Path) -> None:
        """The same URL in two files must result in exactly one HTTP request."""
        url = "https://example.com"
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text(f"[link]({url})")
        (docs / "b.md").write_text(f"[link]({url})")
        mock_ping = AsyncMock(return_value=None)
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        with patch("zenzic.core.validator._ping_url", new=mock_ping):
            validate_links(docs_root, mgr, repo_root=tmp_path, config=config, strict=True)
        assert mock_ping.call_count == 1

    def test_mixed_internal_and_external_errors(self, tmp_path: Path) -> None:
        """Both internal and external errors are returned together."""
        docs = tmp_path / "docs"
        docs.mkdir()
        url = "https://dead.example.com"
        (docs / "index.md").write_text(f"[broken-internal](ghost.md)\n[broken-external]({url})\n")
        err_msg = f"external link '{url}' returned HTTP 404"
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        with patch("zenzic.core.validator._ping_url", new=AsyncMock(return_value=err_msg)):
            errors = validate_links(docs_root, mgr, repo_root=tmp_path, config=config, strict=True)
        assert len(errors) == 2
        assert any("ghost.md" in e for e in errors)
        assert any("404" in e for e in errors)

    def test_semaphore_constant_is_positive_int(self) -> None:
        """Sanity check: concurrency limit must be a positive integer."""
        assert isinstance(_MAX_CONCURRENT_REQUESTS, int)
        assert _MAX_CONCURRENT_REQUESTS > 0


# ─── Python snippet validation (unchanged behaviour) ─────────────────────────


def test_validate_snippets_valid_and_invalid(tmp_path: Path) -> None:
    repo = tmp_path / "my_repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)

    (docs / "valid.md").write_text("# Valid\n```python\ndef add(a, b):\n    return a + b\n```\n")
    (docs / "invalid.md").write_text(
        '# Invalid\n```python title="script.py"\ndef broken(a, b)\n    return a + b\n```\n'
    )
    # Short snippet below min_lines threshold — must be skipped
    (docs / "short.md").write_text("# Short\n```python\nx = 1\n```\n")

    # Excluded directory — must be skipped entirely
    includes = docs / "includes"
    includes.mkdir()
    (includes / "inc.md").write_text("# Inc\n```python\ninvalid syntax here\n```\n")

    config = ZenzicConfig(snippet_min_lines=2, excluded_dirs=["includes"])
    mgr = make_mgr(config, repo_root=repo)
    docs_root = repo / config.docs_dir
    errors = validate_snippets(docs_root, mgr, config=config)

    assert len(errors) == 1
    assert errors[0].file_path.name == "invalid.md"
    assert "SyntaxError in Python snippet" in errors[0].message


def test_validate_snippets_python_indented(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    # Indented code block nested in a list admonition — must still be parsed and validated as Python.
    (docs / "page.md").write_text(
        "    ```python\n    def add(a, b):\n        return a + b\n    ```\n"
    )
    config = ZenzicConfig(snippet_min_lines=1)
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    assert validate_snippets(docs_root, mgr, config=config) == []


def test_validate_snippets_no_code_blocks(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("No code blocks here.")
    config = ZenzicConfig()
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    assert validate_snippets(docs_root, mgr, config=config) == []


def test_validate_snippets_docs_not_exist(tmp_path: Path) -> None:
    config = ZenzicConfig()
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    assert validate_snippets(docs_root, mgr, config=config) == []


def test_validate_snippets_symlink_skipped(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    real_file = outside / "real.md"
    real_file.write_text("```python\ndef broken(\n```")
    (docs / "linked.md").symlink_to(real_file)
    config = ZenzicConfig()
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=docs)
    assert validate_snippets(docs_root, mgr, config=config) == []


def test_validate_snippets_generic_exception_reported(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("```python\nx = 1\n```")
    config = ZenzicConfig(snippet_min_lines=1)
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    with patch("zenzic.core.validator.compile", side_effect=MemoryError("oom")):
        errors = validate_snippets(docs_root, mgr, config=config)
    assert len(errors) == 1
    assert "ParserError" in errors[0].message


# ─── YAML snippet validation ──────────────────────────────────────────────────


def test_validate_snippets_yaml_valid(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("```yaml\nkey: value\nlist:\n  - a\n  - b\n```\n")
    config = ZenzicConfig(snippet_min_lines=1)
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    assert validate_snippets(docs_root, mgr, config=config) == []


def test_validate_snippets_yaml_custom_tags(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text(
        "```yaml\nkey: !ENV [VAR, default]\nanother: !custom {a: b}\n```\n"
    )
    config = ZenzicConfig(snippet_min_lines=1)
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    assert validate_snippets(docs_root, mgr, config=config) == []


def test_validate_snippets_yaml_invalid(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("```yaml\nkey: [\nunclosed bracket\n```\n")
    config = ZenzicConfig(snippet_min_lines=1)
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    errors = validate_snippets(docs_root, mgr, config=config)
    assert len(errors) == 1
    assert "SyntaxError in YAML snippet" in errors[0].message


def test_validate_snippets_yml_alias_invalid(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("```yml\n: bad mapping\n```\n")
    config = ZenzicConfig(snippet_min_lines=1)
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    errors = validate_snippets(docs_root, mgr, config=config)
    assert len(errors) == 1
    assert "SyntaxError in YAML snippet" in errors[0].message


# ─── JSON snippet validation ──────────────────────────────────────────────────


def test_validate_snippets_json_valid(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text('```json\n{"key": "value", "num": 42}\n```\n')
    config = ZenzicConfig(snippet_min_lines=1)
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    assert validate_snippets(docs_root, mgr, config=config) == []


def test_validate_snippets_json_invalid(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text('```json\n{"key": "value",}\n```\n')
    config = ZenzicConfig(snippet_min_lines=1)
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    errors = validate_snippets(docs_root, mgr, config=config)
    assert len(errors) == 1
    assert "SyntaxError in JSON snippet" in errors[0].message


def test_validate_snippets_json_line_number(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    # fence opens at line 3 (two preceding lines), error is on line 2 of snippet
    (docs / "page.md").write_text("# Page\n\n```json\n{\n  bad\n}\n```\n")
    config = ZenzicConfig(snippet_min_lines=1)
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    errors = validate_snippets(docs_root, mgr, config=config)
    assert len(errors) == 1
    # fence_line=3, json error lineno=2 → reported line 5
    assert errors[0].line_no == 5


# ─── TOML snippet validation ──────────────────────────────────────────────────


def test_validate_snippets_toml_valid(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text('```toml\ntitle = "Zenzic"\nversion = "0.4.0"\n```\n')
    config = ZenzicConfig(snippet_min_lines=1)
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    assert validate_snippets(docs_root, mgr, config=config) == []


def test_validate_snippets_toml_invalid(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("```toml\ntitle = Zenzic  # missing quotes\n```\n")
    config = ZenzicConfig(snippet_min_lines=1)
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    errors = validate_snippets(docs_root, mgr, config=config)
    assert len(errors) == 1
    assert "SyntaxError in TOML snippet" in errors[0].message


def test_validate_snippets_with_highlight_comments(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    content = """
```python
# highlight-start
def foo():
    # highlight-next-line
    print("hello")
# highlight-end
```

```yaml
# highlight-start
key: value
# highlight-end
```
"""
    (docs / "page.md").write_text(content)
    config = ZenzicConfig(snippet_min_lines=1)
    docs_root = tmp_path / config.docs_dir
    mgr = make_mgr(config, repo_root=tmp_path)
    errors = validate_snippets(docs_root, mgr, config=config)
    assert errors == [], f"Expected no errors, got: {errors}"


# ─── Cycle detection ──────────────────────────────────────────────────────────


class TestFindCyclesIterative:
    """Unit tests for _find_cycles_iterative (pure function, no I/O)."""

    def test_simple_cycle_ab(self) -> None:
        a = Path("/docs/a.md")
        b = Path("/docs/b.md")
        adj: dict[Path, set[Path]] = {a: {b}, b: {a}}
        result = _find_cycles_iterative(adj)
        assert a.as_posix() in result
        assert b.as_posix() in result

    def test_linear_chain_no_cycle(self) -> None:
        a = Path("/docs/a.md")
        b = Path("/docs/b.md")
        c = Path("/docs/c.md")
        adj: dict[Path, set[Path]] = {a: {b}, b: {c}, c: set()}
        result = _find_cycles_iterative(adj)
        assert result == frozenset()

    def test_self_loop_cycle(self) -> None:
        a = Path("/docs/a.md")
        adj: dict[Path, set[Path]] = {a: {a}}
        result = _find_cycles_iterative(adj)
        assert a.as_posix() in result

    def test_three_node_cycle(self) -> None:
        a = Path("/docs/a.md")
        b = Path("/docs/b.md")
        c = Path("/docs/c.md")
        adj: dict[Path, set[Path]] = {a: {b}, b: {c}, c: {a}}
        result = _find_cycles_iterative(adj)
        assert a.as_posix() in result
        assert b.as_posix() in result
        assert c.as_posix() in result

    def test_isolated_nodes_no_cycle(self) -> None:
        a = Path("/docs/a.md")
        b = Path("/docs/b.md")
        adj: dict[Path, set[Path]] = {a: set(), b: set()}
        assert _find_cycles_iterative(adj) == frozenset()

    def test_acyclic_graph_with_shared_target(self) -> None:
        # A→C and B→C — converging, not a cycle
        a = Path("/docs/a.md")
        b = Path("/docs/b.md")
        c = Path("/docs/c.md")
        adj: dict[Path, set[Path]] = {a: {c}, b: {c}, c: set()}
        assert _find_cycles_iterative(adj) == frozenset()


class TestCircularLinkIntegration:
    """End-to-end: validate_links_structured detects and reports CIRCULAR_LINK."""

    def test_two_file_cycle_emits_circular_link(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("[go to b](b.md)\n")
        (docs / "b.md").write_text("[go to a](a.md)\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links_structured(docs_root, mgr, repo_root=tmp_path, config=config)
        circular = [e for e in errors if e.error_type == "Z106"]
        assert len(circular) == 2  # one from a.md and one from b.md

    def test_linear_chain_no_circular_link(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("[go to b](b.md)\n")
        (docs / "b.md").write_text("[go to c](c.md)\n")
        (docs / "c.md").write_text("# Terminus\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links_structured(docs_root, mgr, repo_root=tmp_path, config=config)
        circular = [e for e in errors if e.error_type == "Z106"]
        assert circular == []

    def test_i18n_cross_language_cycle_detected(self, tmp_path: Path) -> None:
        """EN→IT→EN cross-language cycle must be caught."""
        docs = tmp_path / "docs"
        docs.mkdir()
        it_dir = docs / "it"
        it_dir.mkdir()
        (docs / "guide.md").write_text("[Italian version](it/guide.md)\n")
        (it_dir / "guide.md").write_text("[English version](../guide.md)\n")
        config = ZenzicConfig()
        docs_root = tmp_path / config.docs_dir
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = validate_links_structured(docs_root, mgr, repo_root=tmp_path, config=config)
        circular = [e for e in errors if e.error_type == "Z106"]
        assert len(circular) == 2


# ── CEO-252: check_external=False skips Pass 3 (Environmental Sovereignty) ───


class TestCheckExternalFlag:
    """CEO-252 — --no-external / check_external=False skips HTTP HEAD only."""

    def test_no_external_skips_http_pass(self, tmp_path: Path) -> None:
        """validate_links_async Pass 3 (_check_external_links) is never called
        when check_external=False, even when strict=True.
        """
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[External](https://example.com)\n")
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)

        with patch(
            "zenzic.core.validator._check_external_links",
            new_callable=AsyncMock,
        ) as mock_pass3:
            errors = validate_links_structured(
                docs,
                mgr,
                repo_root=tmp_path,
                config=config,
                strict=True,  # Pass 3 would normally run
                check_external=False,  # R27: skip Pass 3
            )

        mock_pass3.assert_not_called()
        assert errors == []

    def test_check_external_true_allows_pass3(self, tmp_path: Path) -> None:
        """When check_external=True (default) and strict=True, Pass 3 is called."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("[External](https://example.com)\n")
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)

        with patch(
            "zenzic.core.validator._check_external_links",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_pass3:
            validate_links_structured(
                docs,
                mgr,
                repo_root=tmp_path,
                config=config,
                strict=True,
                check_external=True,
            )

        mock_pass3.assert_called_once()

    def test_credential_scanner_fires_with_check_external_false(self, tmp_path: Path) -> None:
        """Credential scanner (Pass 1 via scan_lines_with_lookback) is independent of check_external.

        The credential scanner operates on raw file content and has no concept of check_external.
        This test verifies that (a) validate_links_structured still succeeds when
        check_external=False, and (b) the credential scanner module independently detects the
        credential — confirming they are orthogonal systems.
        """
        from zenzic.core.credentials import scan_lines_with_lookback

        # Construct a fake PAT (Synthetic Test Protocol — D002)
        _prefix = "ghp_"
        _body = "A" * 36
        fake_pat = _prefix + _body

        docs = tmp_path / "docs"
        docs.mkdir()
        file_content = f"[Click here](https://example.com?token={fake_pat})\n"
        md_file = docs / "secret.md"
        md_file.write_text(file_content)
        (tmp_path / ".zenzic.toml").write_text("[project]\n")
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)

        # validate_links_structured with check_external=False must complete without error
        errors = validate_links_structured(
            docs,
            mgr,
            repo_root=tmp_path,
            config=config,
            strict=False,
            check_external=False,
        )
        # No link errors — the PAT is in an external URL, not a broken internal link
        link_errors = [e for e in errors if e.error_type not in ("CREDENTIAL_SECRET", "Z201")]
        assert link_errors == []

        # Independently: the credential scanner detects the credential in raw content
        numbered_lines = enumerate(file_content.splitlines(keepends=True), start=1)
        credential_findings = list(scan_lines_with_lookback(numbered_lines, file_path=md_file))
        assert len(credential_findings) >= 1, (
            "Credential scanner must detect the credential independently of check_external"
        )


def test_validator_short_circuits_analysis_on_z001(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verify that a malformed config structure causes a short-circuit before scanning starts."""
    import sys

    from zenzic.main import cli_main

    repo = tmp_path / "repo"
    repo.mkdir()
    docs = repo / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("[broken](ghost.md)")

    # Write invalid config to trigger Z001
    (repo / ".zenzic.toml").write_text("[governance]\nsuppression_cap = -5\n")

    monkeypatch.chdir(repo)
    monkeypatch.setattr(sys, "argv", ["zenzic", "check", "all"])

    with pytest.raises(SystemExit) as exc_info:
        cli_main()

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    # Verify that the link validation was short-circuited (never actually run)
    assert "ghost.md" not in captured.out
    assert "No broken links found" not in captured.out
    assert "Analysis complete" not in captured.out


def test_cli_z001_outputs_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verify that a Z001 error is correctly formatted as JSON."""
    import json
    import sys

    from zenzic.main import cli_main

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".zenzic.toml").write_text("[governance]\nsuppression_cap = -5\n")

    monkeypatch.chdir(repo)
    monkeypatch.setattr(sys, "argv", ["zenzic", "check", "all", "--format", "json"])

    with pytest.raises(SystemExit) as exc_info:
        cli_main()

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["code"] == "Z001"
    assert data["tier"] == "Core"
    assert data["severity"] == "fatal"
    assert "Configuration validation failed" in data["message"]
    assert ".zenzic.toml" in data["file"]


def test_cli_z001_outputs_sarif(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Verify that a Z001 error is correctly formatted as SARIF."""
    import json
    import sys

    from zenzic.main import cli_main

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".zenzic.toml").write_text("[governance]\nsuppression_cap = -5\n")

    monkeypatch.chdir(repo)
    monkeypatch.setattr(sys, "argv", ["zenzic", "check", "all", "--format", "sarif"])

    with pytest.raises(SystemExit) as exc_info:
        cli_main()

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["version"] == "2.1.0"
    assert "runs" in data
    run = data["runs"][0]
    assert "invocations" in run
    invocation = run["invocations"][0]
    assert invocation["executionSuccessful"] is False
    notification = invocation["toolExecutionNotifications"][0]
    assert notification["descriptor"]["id"] == "Z001"
    assert notification["level"] == "error"
    assert "Configuration validation failed" in notification["message"]["text"]


def test_stale_allowlist_entry(tmp_path: Path) -> None:
    """Verify that Z112 STALE_ALLOWLIST_ENTRY detects unused allowlist entries and maps to origin_file."""
    from zenzic.core.validator import validate_links_structured
    from zenzic.models.config import ZenzicConfig

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text(
        "[Allowed](/allowed/foo.html) [Not Allowed](/notallowed/foo.html)\n"
    )
    (tmp_path / ".zenzic.toml").write_text("[project]\n")

    # Case 1: origin_file is None, falls back to .zenzic.toml
    config = ZenzicConfig(absolute_path_allowlist=["/allowed/", "/unused/"])
    mgr = make_mgr(config, repo_root=tmp_path)

    errors = validate_links_structured(
        docs,
        mgr,
        repo_root=tmp_path,
        config=config,
        strict=False,
        check_external=False,
    )

    z110_errors = [e for e in errors if e.error_type == "Z112"]
    assert len(z110_errors) == 1
    assert z110_errors[0].error_type == "Z112"
    assert "/unused/" in z110_errors[0].message
    assert z110_errors[0].file_path == tmp_path / ".zenzic.toml"
    assert ".zenzic.toml:1: Stale absolute_path_allowlist entry" in z110_errors[0].message

    # Case 2: origin_file is pyproject.toml
    config_pyproject = ZenzicConfig(absolute_path_allowlist=["/allowed/", "/unused/"])
    config_pyproject.origin_file = tmp_path / "pyproject.toml"
    mgr_pyproject = make_mgr(config_pyproject, repo_root=tmp_path)

    errors_pyproject = validate_links_structured(
        docs,
        mgr_pyproject,
        repo_root=tmp_path,
        config=config_pyproject,
        strict=False,
        check_external=False,
    )

    z110_errors_pyproject = [e for e in errors_pyproject if e.error_type == "Z112"]
    assert len(z110_errors_pyproject) == 1
    assert z110_errors_pyproject[0].error_type == "Z112"
    assert "/unused/" in z110_errors_pyproject[0].message
    assert z110_errors_pyproject[0].file_path == tmp_path / "pyproject.toml"
    assert (
        "pyproject.toml:1: Stale absolute_path_allowlist entry" in z110_errors_pyproject[0].message
    )


def test_math_blocks_link_extraction_ignored():
    """Verify that links syntax inside display math ($$..$$) and inline math ($..$) are ignored."""
    from zenzic.core.rules import _extract_inline_links_with_lines
    from zenzic.core.validator import PolyglotExtractor

    content = """# Math Test
$$\\text{Signature} = \\text{SHA256}[\\text{RuleCode} + \\text{PosixPath}](:16)$$
Here is a normal link: [Valid Link](https://example.com/valid).
Inline math $\\text{Ref}[\\text{Code}](:32)$ should also be ignored.
"""
    extractor = PolyglotExtractor()
    extracted = extractor.extract_inline_links(content)
    urls = [e.url for e in extracted]
    assert urls == ["https://example.com/valid"]

    rule_links = _extract_inline_links_with_lines(content)
    rule_urls = [u[0] for u in rule_links]
    assert rule_urls == ["https://example.com/valid"]


def test_polyglot_extractor_multiline_comment_line_preservation():
    """Verify that multiline HTML comments with code blocks inside preserve line numbers for subsequent links."""
    from zenzic.core.validator import PolyglotExtractor

    content = """# Header (Line 1)
Line 2 text
<!--
Line 4 in comment
```python
API_KEY = "sk-live-123"
```
Line 8 in comment
-->
Line 10 text
[Real Link](https://example.com/real)
"""
    extractor = PolyglotExtractor()
    extracted = extractor.extract_all_links(content)

    assert len(extracted) == 1
    link = extracted[0]
    assert link.url == "https://example.com/real"
    assert link.line_no == 11
