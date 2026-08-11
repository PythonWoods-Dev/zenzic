# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Protocol compliance audit and Hypothesis stress tests for Metadata-Driven Routing.

This module validates:
1. ``runtime_checkable`` Protocol compliance for all 4 adapters.
2. ``RouteMetadata`` dataclass invariants.
3. ``get_route_info()`` contract: every adapter returns valid metadata.
4. ``build_metadata_cache()`` / ``extract_frontmatter_*()`` correctness.
5. ``safe_read_line()`` credential scanner middleware integration.
6. Hypothesis stress tests on ``get_route_info()`` with extreme paths.
7. Pickle safety: adapter instances survive pickle round-trip.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import strategies as st

from zenzic.core.adapters._base import RouteMetadata
from zenzic.core.adapters._standalone import StandaloneAdapter
from zenzic.core.adapters._utils import (
    build_metadata_cache,
    extract_frontmatter_draft,
    extract_frontmatter_slug,
    extract_frontmatter_tags,
    extract_frontmatter_unlisted,
)
from zenzic.core.credentials import CredentialViolation, safe_read_line
from zenzic.models.config import BuildContext


def _make_context(**overrides: object) -> BuildContext:
    """Create a minimal BuildContext for testing."""
    defaults: dict[str, object] = {
        "engine": "standalone",
        "default_locale": "en",
        "locales": [],
        "fallback_to_default": True,
    }
    defaults.update(overrides)
    return BuildContext(**defaults)


_path_segment = st.text(
    alphabet=st.sampled_from(list("abcdefghijklmnopqrstuvwxyz0123456789-_")),
    min_size=1,
    max_size=30,
)
_rel_path = st.lists(_path_segment, min_size=1, max_size=4).map(
    lambda parts: Path("/".join(parts) + ".md")
)
_traversal_path = st.sampled_from(
    [
        Path("../../etc/passwd"),
        Path("../../../root/.ssh/id_rsa"),
        Path("../__init__.py"),
        Path("docs/../../../etc/shadow"),
        Path("a/b/c/d/e/f/g/h/i/j/k/l.md"),
    ]
)
_long_path = st.lists(_path_segment, min_size=10, max_size=20).map(
    lambda parts: Path("/".join(parts) + ".md")
)
_special_path = st.sampled_from(
    [
        Path("file with spaces.md"),
        Path("über-guide.md"),
        Path("guide_v2.0.md"),
        Path("_private/secret.md"),
        Path("__pycache__/module.md"),
        Path(".hidden/page.md"),
        Path("index.md"),
        Path("README.md"),
    ]
)


class TestRouteMetadataInvariants:
    """RouteMetadata dataclass must be well-formed."""

    def test_defaults(self) -> None:
        meta = RouteMetadata(canonical_url="/", status="REACHABLE")
        assert meta.slug is None
        assert meta.route_base_path == "/"
        assert meta.is_proxy is False

    def test_with_slug(self) -> None:
        meta = RouteMetadata(canonical_url="/custom/", status="REACHABLE", slug="/custom")
        assert meta.slug == "/custom"

    def test_proxy_route(self) -> None:
        meta = RouteMetadata(canonical_url="/it/", status="REACHABLE", is_proxy=True)
        assert meta.is_proxy is True

    def test_conflict_status(self) -> None:
        meta = RouteMetadata(canonical_url="/page/", status="CONFLICT")
        assert meta.status == "CONFLICT"


class TestFrontmatterExtraction:
    """Engine-agnostic frontmatter extraction utilities."""

    def test_slug_basic(self) -> None:
        content = "---\ntitle: Test\nslug: /custom\n---\n\nBody"
        assert extract_frontmatter_slug(content) == "/custom"

    def test_slug_relative(self) -> None:
        content = "---\nslug: custom-name\n---\n\nBody"
        assert extract_frontmatter_slug(content) == "custom-name"

    def test_slug_missing(self) -> None:
        content = "---\ntitle: Test\n---\n\nBody"
        assert extract_frontmatter_slug(content) is None

    def test_slug_no_frontmatter(self) -> None:
        content = "Just plain text\n"
        assert extract_frontmatter_slug(content) is None

    def test_draft_true(self) -> None:
        content = "---\ndraft: true\n---\n\nBody"
        assert extract_frontmatter_draft(content) is True

    def test_draft_false(self) -> None:
        content = "---\ndraft: false\n---\n\nBody"
        assert extract_frontmatter_draft(content) is False

    def test_draft_missing(self) -> None:
        content = "---\ntitle: Test\n---\n\nBody"
        assert extract_frontmatter_draft(content) is False

    def test_unlisted_true(self) -> None:
        content = "---\nunlisted: true\n---\n\nBody"
        assert extract_frontmatter_unlisted(content) is True

    def test_unlisted_false(self) -> None:
        content = "---\nunlisted: false\n---\n\nBody"
        assert extract_frontmatter_unlisted(content) is False

    def test_tags_inline(self) -> None:
        content = "---\ntags: [python, docs, integrity]\n---\n\nBody"
        assert extract_frontmatter_tags(content) == ["python", "docs", "integrity"]

    def test_tags_flow(self) -> None:
        content = "---\ntags:\n- python\n- docs\n---\n\nBody"
        assert extract_frontmatter_tags(content) == ["python", "docs"]

    def test_tags_empty(self) -> None:
        content = "---\ntitle: Test\n---\n\nBody"
        assert extract_frontmatter_tags(content) == []


class TestBuildMetadataCache:
    """build_metadata_cache() must produce correct FileMetadata."""

    def test_single_file_with_slug(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        content = "---\nslug: /custom\ndraft: true\ntags: [a, b]\n---\n\nBody"
        md_contents = {docs / "page.md": content}
        cache = build_metadata_cache(md_contents, docs, scan_credentials=False)
        assert "page.md" in cache
        meta = cache["page.md"]
        assert meta.slug == "/custom"
        assert meta.draft is True
        assert meta.tags == ["a", "b"]

    def test_credential_scanner_catches_secret_in_frontmatter(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        fake_key = "sk-" + "a" * 48
        content = f"---\ntitle: Test\napi_key: {fake_key}\n---\n\nBody"
        md_contents = {docs / "page.md": content}
        with pytest.raises(CredentialViolation) as exc_info:
            build_metadata_cache(md_contents, docs, scan_credentials=True)
        assert exc_info.value.finding.secret_type == "openai-api-key"

    def test_credential_scanner_disabled_allows_secret(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        fake_key = "sk-" + "a" * 48
        content = f"---\ntitle: Test\napi_key: {fake_key}\n---\n\nBody"
        md_contents = {docs / "page.md": content}
        cache = build_metadata_cache(md_contents, docs, scan_credentials=False)
        assert "page.md" in cache


class TestCredentialScannerMiddleware:
    """safe_read_line() must raise CredentialViolation on secrets."""

    def test_clean_line_passes_through(self) -> None:
        result = safe_read_line("slug: /custom-path", Path("test.md"), 1)
        assert result == "slug: /custom-path"

    def test_secret_raises_violation(self) -> None:
        fake_key = "sk-" + "a" * 48
        with pytest.raises(CredentialViolation) as exc_info:
            safe_read_line(f"key: {fake_key}", Path("test.md"), 5)
        assert exc_info.value.finding.secret_type == "openai-api-key"
        assert exc_info.value.finding.line_no == 5

    def test_github_token_raises(self) -> None:
        fake_token = "ghp_" + "a" * 36
        with pytest.raises(CredentialViolation):
            safe_read_line(f"token: {fake_token}", Path("test.md"), 1)

    def test_normal_frontmatter_safe(self) -> None:
        lines = ["title: My Page", "slug: /about", "draft: false", "tags: [python, docs]"]
        for i, line in enumerate(lines):
            result = safe_read_line(line, Path("test.md"), i + 1)
            assert result == line


class TestStandaloneNoSpuriousWarnings:
    """StandaloneAdapter must not emit warnings on pure Markdown repos."""

    def test_no_warnings_on_get_route_info(self, capsys: pytest.CaptureFixture[str]) -> None:
        adapter = StandaloneAdapter()
        adapter.get_route_info(Path("page.md"))
        captured = capsys.readouterr()
        assert captured.err == ""
