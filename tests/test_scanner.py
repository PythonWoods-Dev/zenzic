# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for Zenzic scanner (orphans, placeholders, root discovery)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml
from _helpers import make_mgr

from zenzic.core.adapter import _extract_i18n_locale_dirs, _extract_i18n_locale_patterns
from zenzic.core.rules import BrandObsolescenceRule, PlaceholderRule, ShortContentRule
from zenzic.core.scanner import (
    find_orphans,
    find_repo_root,
    find_unused_assets,
)
from zenzic.models.config import ProjectMetadata, ZenzicConfig


def test_find_repo_root_success(tmp_path: Path) -> None:
    repo = tmp_path / "my_repo"
    repo.mkdir()
    (repo / ".zenzic.toml").touch()
    deep_dir = repo / "docs" / "nested" / "dir"
    deep_dir.mkdir(parents=True)
    original_cwd = Path.cwd()
    os.chdir(deep_dir)
    try:
        found = find_repo_root()
        assert found == repo.resolve()
    finally:
        os.chdir(original_cwd)


def test_find_repo_root_failure(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    original_cwd = Path.cwd()
    os.chdir(empty_dir)
    try:
        with pytest.raises(RuntimeError, match="Could not locate repo root"):
            find_repo_root()
    finally:
        os.chdir(original_cwd)


def test_find_orphans(tmp_path: Path) -> None:
    repo = tmp_path / "my_repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    nav = {"nav": ["index.md", {"API": "api.md"}, {"Nested": [{"Sub": "nested/page.md"}]}]}
    with (repo / "mkdocs.yml").open("w") as f:
        yaml.dump(nav, f)
    (docs / "index.md").touch()
    (docs / "api.md").touch()
    (docs / "nested").mkdir()
    (docs / "nested/page.md").touch()
    (docs / "orphan1.md").touch()
    (docs / "nested/orphan2.md").touch()
    (docs / "includes").mkdir()
    (docs / "includes/snippet.md").touch()
    config = ZenzicConfig(excluded_dirs=["includes"])
    mgr = make_mgr(config, repo_root=repo)
    orphans = find_orphans(docs, mgr, repo_root=repo, config=config)
    orphan_paths = [p.as_posix() for p in orphans]
    assert "orphan1.md" in orphan_paths
    assert "nested/orphan2.md" in orphan_paths
    assert "index.md" not in orphan_paths
    assert "api.md" not in orphan_paths
    assert "includes/snippet.md" not in orphan_paths
    assert len(orphans) == 2


def test_find_repo_root_via_git(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    deep = repo / "src" / "pkg"
    deep.mkdir(parents=True)
    original_cwd = Path.cwd()
    os.chdir(deep)
    try:
        assert find_repo_root() == repo.resolve()
    finally:
        os.chdir(original_cwd)


def test_find_repo_root_genesis_fallback(tmp_path: Path) -> None:
    """ZRT-005: fallback_to_cwd=True must return CWD in an empty directory."""
    empty = tmp_path / "brand_new_project"
    empty.mkdir()
    original_cwd = Path.cwd()
    os.chdir(empty)
    try:
        result = find_repo_root(fallback_to_cwd=True)
        assert result == empty.resolve()
    finally:
        os.chdir(original_cwd)


def test_find_repo_root_genesis_fallback_still_raises_without_flag(tmp_path: Path) -> None:
    """ZRT-005: default behaviour (fallback_to_cwd=False) still raises in empty dirs."""
    empty = tmp_path / "no_root"
    empty.mkdir()
    original_cwd = Path.cwd()
    os.chdir(empty)
    try:
        with pytest.raises(RuntimeError, match="Could not locate repo root"):
            find_repo_root()
    finally:
        os.chdir(original_cwd)


def test_find_orphans_no_config(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    nav = {"nav": [{"Home": "index.md"}]}
    with (repo / "mkdocs.yml").open("w") as f:
        yaml.dump(nav, f)
    (docs / "index.md").touch()
    (docs / "extra.md").touch()
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=repo)
    orphans = find_orphans(docs, mgr, repo_root=repo, config=config)
    assert len(orphans) == 1


def test_find_orphans_config_file_missing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=repo)
    docs_root = repo / config.docs_dir
    orphans = find_orphans(docs_root, mgr, repo_root=repo, config=config)
    assert orphans == []


def test_find_orphans_invalid_yaml(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (repo / "mkdocs.yml").write_text("nav: [: invalid")
    (docs / "page.md").touch()
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=repo)
    orphans = find_orphans(docs, mgr, repo_root=repo, config=config)
    assert orphans == []


def test_find_orphans_symlink_skipped(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    nav = {"nav": [{"Home": "index.md"}]}
    with (repo / "mkdocs.yml").open("w") as f:
        yaml.dump(nav, f)
    (docs / "index.md").touch()
    real = tmp_path / "real.md"
    real.touch()
    (docs / "linked.md").symlink_to(real)
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=repo)
    orphans = find_orphans(docs, mgr, repo_root=repo, config=config)
    assert all(p.name != "linked.md" for p in orphans)


def test_find_orphans_docs_not_exist(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "mkdocs.yml").write_text("nav:\n  - Home: index.md\n")
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=repo)
    docs_root = repo / config.docs_dir
    orphans = find_orphans(docs_root, mgr, repo_root=repo, config=config)
    assert orphans == []


def test_placeholder_mdx_comments_excluded_from_word_count() -> None:
    """MDX {/* … */} and HTML <!-- … --> comments must not count as prose words.

    Regression: docs/community/license.mdx had <10 visible words but was not
    flagged because its {/* … */} comment block (70+ words) inflated the count.
    """
    text = '---\nsidebar_label: "License"\ndescription: "Licensing information."\n---\n\n# License\n\n{/*\nThis page uses the pymdownx snippets extension to include the root LICENSE file\ndirectly — single source of truth, no divergence possible.\n\nBelow, we add some extra explanation text about how this license applies to the\nZenzic documentation and source code, as required to provide more context to our users\nand to pass internal minimum content validation checks within our own linting loops.\n*/}\n\nSee LICENSE file.\n'
    config = ZenzicConfig(placeholder_max_words=50)
    rule = ShortContentRule(config.placeholder_max_words)
    findings = rule.check(Path("community/license.mdx"), text)
    assert any(f.rule_id == "Z502" for f in findings), (
        "Page with MDX-comment-inflated word count must still be flagged as short-content"
    )


def test_short_content_pointer_skips_frontmatter() -> None:
    """Z502 short-content finding must point to the first content line, not to frontmatter.

    Regression (D048 Bug 1): line_no was hardcoded to 1, causing the red arrow ``❱``
    to point at the opening ``---`` of the frontmatter block, misleading users into
    thinking frontmatter words were being counted as content.
    """
    text = "---\nicon: SafetyCheck\nsidebar_label: Licenza\ntitle: Licenza Apache 2.0\ndescription: Informazioni sulla licenza.\n---\n\n# Licenza\n\nLICENZA\n"
    config = ZenzicConfig(placeholder_max_words=50)
    rule = ShortContentRule(config.placeholder_max_words)
    findings = rule.check(Path("community/license.mdx"), text)
    short = [f for f in findings if f.rule_id == "Z502"]
    assert short, "Page with 3 visible words must trigger short-content"
    assert short[0].line_no > 1, (
        f"short-content finding points at line {short[0].line_no} — expected a line past the frontmatter block"
    )


def test_jsx_suppression_is_respected_for_z601() -> None:
    """MDX-native JSX suppression marker must silence Z601 on the tagged line."""
    rule = BrandObsolescenceRule(
        ProjectMetadata(
            release_name="v0.8.0", obsolete_names=["v0.6.x"], obsolete_names_exclude_patterns=[]
        )
    )
    text = "v0.6.x codename {/* zenzic:ignore: Z601 release codename */}\n"
    findings = rule.check(Path("docs/page.mdx"), text)
    assert findings == []


def test_html_suppression_still_works_for_z601() -> None:
    """Legacy/standard HTML suppression marker remains backward compatible."""
    rule = BrandObsolescenceRule(
        ProjectMetadata(
            release_name="v0.8.0", obsolete_names=["v0.6.x"], obsolete_names_exclude_patterns=[]
        )
    )
    text = "v0.6.x codename <!-- zenzic:ignore: Z601 release codename -->\n"
    findings = rule.check(Path("docs/page.md"), text)
    assert findings == []


def test_short_content_pointer_skips_spdx_comments() -> None:
    """Z502 short-content finding must skip leading SPDX HTML comments when computing line_no.

    Regression (D072 — The Ghost Content Fix): ``_first_content_line`` was anchored to
    ``\\A`` via the frontmatter regex and returned line 1 whenever the file opened with
    ``<!-- SPDX … -->`` comments, causing the red arrow ``❱`` to point at the licence
    header instead of the first prose word.
    """
    text = "<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->\n<!-- SPDX-License-Identifier: Apache-2.0 -->\n<!-- SPDX-FileCopyrightText: 2024 Contributor A -->\n<!-- SPDX-License-Identifier: MIT -->\n<!-- Internal audit marker: approved -->\n\n---\ntitle: SPDX Trap\nsidebar_label: Trap\ndescription: Regression test for comment-aware pointer.\nicon: lock\ndraft: true\ntags: [test, spdx]\nkeywords: [regression]\nversion: 0.7.0\n---\n\nFINE\n"
    config = ZenzicConfig(placeholder_max_words=50)
    rule = ShortContentRule(config.placeholder_max_words)
    findings = rule.check(Path("spdx-trap.md"), text)
    short = [f for f in findings if f.rule_id == "Z502"]
    assert short, "File with single word 'FINE' must trigger short-content"
    assert "Page has only 1 words" in short[0].message
    target_line = text.splitlines()[short[0].line_no - 1]
    assert target_line.strip() == "FINE", (
        f"short-content pointer at line {short[0].line_no} is {target_line!r}; expected the line containing 'FINE'"
    )


def test_short_content_pointer_skips_multiline_html_comment() -> None:
    """_first_content_line must traverse a multi-line HTML comment (in_html=True path).

    Covers the ``in_html`` continuation branch — lines 209-213, 221 in scanner.py.
    When ``<!--`` and ``-->`` appear on different lines the walker must consume
    every continuation line before recognising prose content.
    """
    text = "<!--\n SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>\n SPDX-License-Identifier: Apache-2.0\n-->\n\nBrief.\n"
    config = ZenzicConfig(placeholder_max_words=50)
    rule = ShortContentRule(config.placeholder_max_words)
    findings = rule.check(Path("multi-html.mdx"), text)
    short = [f for f in findings if f.rule_id == "Z502"]
    assert short, "Single-word prose must trigger short-content"
    target_line = text.splitlines()[short[0].line_no - 1]
    assert target_line.strip() == "Brief.", (
        f"Pointer at line {short[0].line_no} is {target_line!r}; expected 'Brief.'"
    )


def test_short_content_pointer_skips_multiline_mdx_comment() -> None:
    """_first_content_line must traverse a multi-line MDX comment (in_mdx=True path).

    Covers the ``in_mdx`` continuation branch — lines 214-218, 226 in scanner.py.
    When ``{/*`` and ``*/`` appear on different lines the walker must consume
    every continuation line before recognising prose content.
    """
    text = "{/*\n SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>\n SPDX-License-Identifier: Apache-2.0\n*/}\n\nNote.\n"
    config = ZenzicConfig(placeholder_max_words=50)
    rule = ShortContentRule(config.placeholder_max_words)
    findings = rule.check(Path("multi-mdx.mdx"), text)
    short = [f for f in findings if f.rule_id == "Z502"]
    assert short, "Single-word prose must trigger short-content"
    target_line = text.splitlines()[short[0].line_no - 1]
    assert target_line.strip() == "Note.", (
        f"Pointer at line {short[0].line_no} is {target_line!r}; expected 'Note.'"
    )


def test_short_content_pointer_unclosed_frontmatter() -> None:
    """_first_content_line handles frontmatter with no closing ``---`` (EOF branch).

    Covers the ``if i < n:`` False branch at line 239 in scanner.py — when the
    frontmatter opening ``---`` is found but EOF is reached before the closing ``---``.
    The function must not raise; it returns the line after the last consumed line.
    """
    text = "---\ntitle: Unclosed\nsidebar_label: Unclosed\n"
    config = ZenzicConfig(placeholder_max_words=50)
    rule = ShortContentRule(config.placeholder_max_words)
    findings = rule.check(Path("unclosed-fm.mdx"), text)
    short = [f for f in findings if f.rule_id == "Z502"]
    assert short, "Near-empty file must trigger short-content"
    assert short[0].line_no >= 1


def test_find_unused_assets_no_config(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    assets = docs / "assets"
    assets.mkdir()
    (assets / "img.png").touch()
    (docs / "index.md").write_text("No images here.")
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=tmp_path)
    unused = find_unused_assets(docs, mgr, config=config)
    assert any(p.name == "img.png" for p in unused)


def test_find_unused_assets_docs_not_exist(tmp_path: Path) -> None:
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=tmp_path)
    docs_root = tmp_path / config.docs_dir
    unused = find_unused_assets(docs_root, mgr, config=config)
    assert unused == []


def test_find_orphans_excluded_file_patterns(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    nav = {"nav": [{"Home": "index.md"}]}
    with (repo / "mkdocs.yml").open("w") as f:
        yaml.dump(nav, f)
    (docs / "index.md").touch()
    (docs / "index.it.md").touch()
    config = ZenzicConfig(excluded_file_patterns=["*.it.md"])
    mgr = make_mgr(config, repo_root=repo)
    orphans = find_orphans(docs, mgr, repo_root=repo, config=config)
    assert orphans == []


def test_find_orphans_respects_mkdocs_route_classification(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    docs = repo / "docs"
    (docs / "guide").mkdir(parents=True)
    nav = {"nav": [{"Docs": [{"Overview": "guide/index.md"}]}]}
    with (repo / "mkdocs.yml").open("w") as f:
        yaml.dump(nav, f)
    (docs / "guide" / "index.md").write_text("# Overview\n")
    (docs / "guide" / "orphan.md").write_text("# Orphan\n")
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=repo)
    orphans = find_orphans(docs, mgr, repo_root=repo, config=config)
    orphan_paths = {p.as_posix() for p in orphans}
    assert "guide/index.md" not in orphan_paths
    assert "guide/orphan.md" in orphan_paths


def test_unlisted_file_detection(tmp_path: Path) -> None:
    """A file on disk but absent from nav must be reported as an orphan.

    Regression guard: mkdocs.yml can include Python-tagged YAML values such as
    !!python/name in markdown_extensions. These must not cause nav parsing to
    collapse to an empty dict, otherwise every file is incorrectly marked
    REACHABLE.
    """
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    (repo / "mkdocs.yml").write_text(
        "\n".join(
            [
                "site_name: Test Docs",
                "nav:",
                "  - Home: index.md",
                "markdown_extensions:",
                "  - pymdownx.superfences:",
                "      custom_fences:",
                "        - name: mermaid",
                "          class: mermaid",
                "          format: !!python/name:pymdownx.superfences.fence_code_format",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    (docs / "spy.md").write_text("# Spy\n", encoding="utf-8")
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=repo)
    orphans = find_orphans(docs, mgr, repo_root=repo, config=config)
    orphan_paths = {p.as_posix() for p in orphans}
    assert "spy.md" in orphan_paths
    assert "index.md" not in orphan_paths


def test_extract_i18n_locale_patterns_suffix_mode() -> None:
    doc_config = {
        "plugins": [
            {
                "i18n": {
                    "docs_structure": "suffix",
                    "languages": [
                        {"locale": "en", "default": True},
                        {"locale": "it"},
                        {"locale": "fr"},
                    ],
                }
            }
        ]
    }
    patterns = _extract_i18n_locale_patterns(doc_config)
    assert patterns == {"*.it.md", "*.fr.md"}


def test_extract_i18n_locale_patterns_folder_mode() -> None:
    doc_config = {
        "plugins": [
            {
                "i18n": {
                    "docs_structure": "folder",
                    "languages": [{"locale": "en", "default": True}, {"locale": "it"}],
                }
            }
        ]
    }
    patterns = _extract_i18n_locale_patterns(doc_config)
    assert patterns == set()


def test_extract_i18n_locale_patterns_no_plugin() -> None:
    assert _extract_i18n_locale_patterns({}) == set()
    assert _extract_i18n_locale_patterns({"plugins": ["search"]}) == set()


def test_find_orphans_i18n_auto_detect_mkdocs(tmp_path: Path) -> None:
    """i18n plugin in mkdocs.yml; nav also from mkdocs.yml."""
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    mkdocs_content = {
        "nav": [{"Home": "index.md"}],
        "plugins": [
            {
                "i18n": {
                    "docs_structure": "suffix",
                    "languages": [
                        {"locale": "en", "default": True},
                        {"locale": "it"},
                        {"locale": "fr"},
                    ],
                }
            }
        ],
    }
    with (repo / "mkdocs.yml").open("w") as f:
        yaml.dump(mkdocs_content, f)
    (docs / "index.md").touch()
    (docs / "index.it.md").touch()
    (docs / "index.fr.md").touch()
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=repo)
    orphans = find_orphans(docs, mgr, repo_root=repo, config=config)
    assert orphans == []


def test_extract_i18n_locale_dirs_folder_mode() -> None:
    """Non-default locale dirs returned when docs_structure is 'folder'."""
    doc_config = {
        "plugins": [
            {
                "i18n": {
                    "docs_structure": "folder",
                    "languages": [
                        {"locale": "en", "default": True},
                        {"locale": "it"},
                        {"locale": "fr"},
                    ],
                }
            }
        ]
    }
    assert _extract_i18n_locale_dirs(doc_config) == {"it", "fr"}


def test_extract_i18n_locale_dirs_suffix_mode_returns_empty() -> None:
    """Suffix mode is handled by _extract_i18n_locale_patterns — dirs returns empty."""
    doc_config = {
        "plugins": [
            {
                "i18n": {
                    "docs_structure": "suffix",
                    "languages": [{"locale": "en", "default": True}, {"locale": "it"}],
                }
            }
        ]
    }
    assert _extract_i18n_locale_dirs(doc_config) == set()


def test_extract_i18n_locale_dirs_no_plugin() -> None:
    """Returns empty set when no i18n plugin is configured."""
    assert _extract_i18n_locale_dirs({}) == set()
    assert _extract_i18n_locale_dirs({"plugins": ["search"]}) == set()


def test_extract_i18n_locale_dirs_defensive_none_inputs() -> None:
    """Never raises — returns empty set for malformed / missing keys.

    Regression guard for projects without i18n: _extract_i18n_locale_dirs
    must be safe to call on any dict, including one with None-valued keys.
    """
    assert _extract_i18n_locale_dirs({"plugins": None}) == set()
    assert _extract_i18n_locale_dirs({"plugins": [{"i18n": None}]}) == set()
    assert _extract_i18n_locale_dirs({"plugins": [{"i18n": {"docs_structure": "folder"}}]}) == set()
    assert (
        _extract_i18n_locale_dirs(
            {"plugins": [{"i18n": {"docs_structure": "folder", "languages": None}}]}
        )
        == set()
    )


def test_i18n_languages_is_null(tmp_path: Path) -> None:
    """Scenario: i18n plugin with 'languages: null' in YAML must not raise.

    YAML snippet::

        plugins:
          - i18n:
              languages: null

    Zenzic must return set() and find_orphans must not crash.
    This is the exact YAML pattern the Tech Lead flagged.
    """
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    yaml_content = "nav:\n  - Home: index.md\nplugins:\n  - i18n:\n      docs_structure: folder\n      languages: null\n"
    (repo / "mkdocs.yml").write_text(yaml_content)
    (docs / "index.md").touch()
    import yaml as _yaml

    from zenzic.core.adapter import _PermissiveYamlLoader

    doc_config = _yaml.load(yaml_content, Loader=_PermissiveYamlLoader) or {}
    assert _extract_i18n_locale_dirs(doc_config) == set()
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=repo)
    orphans = find_orphans(docs, mgr, repo_root=repo, config=config)
    assert orphans == []


def test_extract_i18n_locale_dirs_scenario_standalone() -> None:
    """Scenario 'Standalone': mkdocs.yml without any plugin returns empty set.

    Zenzic must be a safe drop-in for projects that have not yet adopted i18n.
    """
    assert _extract_i18n_locale_dirs({}) == set()
    assert _extract_i18n_locale_dirs({"plugins": ["search", "minify"]}) == set()
    assert (
        _extract_i18n_locale_dirs({"site_name": "My Docs", "nav": [{"Home": "index.md"}]}) == set()
    )


def test_extract_i18n_locale_dirs_scenario_broken_config() -> None:
    """Scenario 'Broken Config': malformed i18n block never raises — always set().

    Zenzic does not correct user configuration; it only avoids crashing.
    Edge cases covered:
    - languages is a scalar string instead of a list
    - languages contains non-dict items (ints, nulls)
    - locale key is present but empty string
    - docs_structure key is absent entirely
    """
    assert (
        _extract_i18n_locale_dirs(
            {"plugins": [{"i18n": {"docs_structure": "folder", "languages": "it"}}]}
        )
        == set()
    )
    assert (
        _extract_i18n_locale_dirs(
            {"plugins": [{"i18n": {"docs_structure": "folder", "languages": [None, 42, "it"]}}]}
        )
        == set()
    )
    assert (
        _extract_i18n_locale_dirs(
            {
                "plugins": [
                    {
                        "i18n": {
                            "docs_structure": "folder",
                            "languages": [{"locale": "", "default": False}],
                        }
                    }
                ]
            }
        )
        == set()
    )
    assert (
        _extract_i18n_locale_dirs({"plugins": [{"i18n": {"languages": [{"locale": "it"}]}}]})
        == set()
    )


def test_extract_i18n_locale_dirs_default_locale_excluded() -> None:
    """The default locale is never returned — only non-default translations."""
    doc_config = {
        "plugins": [
            {"i18n": {"docs_structure": "folder", "languages": [{"locale": "en", "default": True}]}}
        ]
    }
    assert _extract_i18n_locale_dirs(doc_config) == set()


def test_find_orphans_folder_i18n_excludes_locale_dirs(tmp_path: Path) -> None:
    """Files inside non-default locale dirs are NOT flagged as orphans (folder mode)."""
    repo = tmp_path / "repo"
    docs = repo / "docs"
    (docs / "it").mkdir(parents=True)
    mkdocs_config = {
        "nav": [{"Home": "index.md"}],
        "plugins": [
            {
                "i18n": {
                    "docs_structure": "folder",
                    "languages": [{"locale": "en", "default": True}, {"locale": "it"}],
                }
            }
        ],
    }
    with (repo / "mkdocs.yml").open("w") as f:
        yaml.dump(mkdocs_config, f)
    (docs / "index.md").touch()
    (docs / "it" / "index.md").touch()
    (docs / "orphan.md").touch()
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=repo)
    orphans = find_orphans(docs, mgr, repo_root=repo, config=config)
    orphan_posix = [p.as_posix() for p in orphans]
    assert "orphan.md" in orphan_posix
    assert "it/index.md" not in orphan_posix
    assert len(orphans) == 1


def test_find_orphans_folder_i18n_nested_file_excluded(tmp_path: Path) -> None:
    """Files nested inside a locale dir (e.g. it/guide/install.md) are also excluded."""
    repo = tmp_path / "repo"
    docs = repo / "docs"
    (docs / "it" / "guide").mkdir(parents=True)
    with (repo / "mkdocs.yml").open("w") as f:
        yaml.dump(
            {
                "nav": [{"Home": "index.md"}],
                "plugins": [
                    {
                        "i18n": {
                            "docs_structure": "folder",
                            "languages": [{"locale": "en", "default": True}, {"locale": "it"}],
                        }
                    }
                ],
            },
            f,
        )
    (docs / "index.md").touch()
    (docs / "it" / "index.md").touch()
    (docs / "it" / "guide" / "install.md").touch()
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=repo)
    orphans = find_orphans(docs, mgr, repo_root=repo, config=config)
    assert orphans == []


def test_find_unused_assets_symlink_skipped(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    real = outside / "real.md"
    real.write_text("![img](assets/img.png)")
    (docs / "linked.md").symlink_to(real)
    assets = docs / "assets"
    assets.mkdir()
    (assets / "img.png").touch()
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=docs)
    unused = find_unused_assets(docs, mgr, config=config)
    assert any(p.name == "img.png" for p in unused)


def test_find_unused_assets_skips_system_infrastructure_files(tmp_path: Path) -> None:
    """System infrastructure files must never appear as Z405 findings.

    Regression (D050): when docs_root == project root, toolchain files like
    package.json were included in the asset walk and emitted spurious Z405
    warnings. The Level 1a guardrail in find_unused_assets must filter them.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Hello\n")
    (docs / "package.json").write_text("{}")
    (docs / "pyproject.toml").write_text("[project]")
    (docs / "yarn.lock").write_text("")
    (docs / "eslint.config.mjs").write_text("export default {};")
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=tmp_path)
    unused = find_unused_assets(docs, mgr, config=config)
    infra_names = {p.name for p in unused}
    assert "package.json" not in infra_names, "package.json must be excluded (L1a)"
    assert "pyproject.toml" not in infra_names, "pyproject.toml must be excluded (L1a)"
    assert "yarn.lock" not in infra_names, "yarn.lock must be excluded (L1a)"
    assert "eslint.config.mjs" not in infra_names, "eslint.config.mjs must be excluded (L1a)"


def test_find_unused_assets_skips_adapter_metadata_files(tmp_path: Path) -> None:
    """Adapter metadata files must be excluded via the adapter_metadata_files param.

    Regression (D050): docusaurus.config.ts in docs_root triggered Z405 when
    the Docusaurus adapter's metadata files were not passed to find_unused_assets.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Hello\n")
    (docs / "docusaurus.config.ts").write_text("export default {};")
    (docs / "sidebars.ts").write_text("export default {};")
    (docs / "logo.png").write_bytes(b"\x89PNG")
    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=tmp_path)
    adapter_meta = frozenset({"docusaurus.config.ts", "sidebars.ts"})
    unused = find_unused_assets(docs, mgr, config=config, adapter_metadata_files=adapter_meta)
    unused_names = {p.name for p in unused}
    assert "docusaurus.config.ts" not in unused_names, "adapter config must be excluded (L1b)"
    assert "sidebars.ts" not in unused_names, "adapter sidebar must be excluded (L1b)"
    assert "logo.png" in unused_names, "genuine unused asset must still be reported"


def test_placeholder_xxx_removed_from_defaults() -> None:
    config = ZenzicConfig()
    assert all("xxx" not in pat for pat in config.placeholder_patterns)
    rule = PlaceholderRule(config.placeholder_patterns_compiled)
    findings = rule.check(Path("test.md"), "This is xxx section.")
    assert not any(f.rule_id == "Z501" for f in findings)


def test_placeholder_partial_files_word_count_skipped() -> None:
    config = ZenzicConfig(placeholder_max_words=50)
    rule = ShortContentRule(config.placeholder_max_words)
    findings_reg = rule.check(Path("test.md"), "Short page.")
    assert any(f.rule_id == "Z502" for f in findings_reg)
    findings_partial = rule.check(Path("_partial.md"), "Short page.")
    assert not any(f.rule_id == "Z502" for f in findings_partial)
