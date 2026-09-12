# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Nav-contract consistency check tests — Virtual Site Map (VSM) based.

check_nav_contract() projects the full set of URLs the build engine will
generate from the docs/ source tree (generate_virtual_site_map), then
validates every extra.alternate link against that map.  No heuristics —
if a link is not in the VSM, it is a 404.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from _helpers import make_mgr

from zenzic.core.validator import check_nav_contract, generate_virtual_site_map
from zenzic.models.config import ZenzicConfig


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _write_mkdocs(repo: Path, content: dict) -> None:  # type: ignore[type-arg]
    with (repo / "mkdocs.yml").open("w", encoding="utf-8") as f:
        yaml.dump(content, f, default_flow_style=False, allow_unicode=True)


def _make_docs(repo: Path, files: list[str]) -> None:
    """Create stub .md files under repo/docs/."""
    docs = repo / "docs"
    docs.mkdir(exist_ok=True)
    for rel in files:
        p = docs / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()


# ─── Unit tests: generate_virtual_site_map (pure function) ───────────────────


class TestGenerateVirtualSiteMap:
    def test_index_md_maps_to_root(self, tmp_path: Path) -> None:
        _make_docs(tmp_path, ["index.md"])
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        vsm = generate_virtual_site_map(tmp_path / "docs", "suffix", mgr)
        assert "/" in vsm

    def test_page_md_maps_to_slash_page_slash(self, tmp_path: Path) -> None:
        _make_docs(tmp_path, ["checks.md"])
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        vsm = generate_virtual_site_map(tmp_path / "docs", "suffix", mgr)
        assert "/checks/" in vsm

    def test_locale_suffix_file_maps_correctly(self, tmp_path: Path) -> None:
        _make_docs(tmp_path, ["checks.it.md"])
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        vsm = generate_virtual_site_map(tmp_path / "docs", "suffix", mgr)
        assert "/checks.it/" in vsm

    def test_nested_index_maps_to_dir(self, tmp_path: Path) -> None:
        _make_docs(tmp_path, ["about/index.md"])
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        vsm = generate_virtual_site_map(tmp_path / "docs", "suffix", mgr)
        assert "/about/" in vsm

    def test_nested_page_maps_correctly(self, tmp_path: Path) -> None:
        _make_docs(tmp_path, ["about/license.md"])
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        vsm = generate_virtual_site_map(tmp_path / "docs", "suffix", mgr)
        assert "/about/license/" in vsm

    def test_empty_docs_returns_empty(self, tmp_path: Path) -> None:
        (tmp_path / "docs").mkdir()
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        vsm = generate_virtual_site_map(tmp_path / "docs", "suffix", mgr)
        assert vsm == frozenset()

    def test_nonexistent_docs_returns_empty(self, tmp_path: Path) -> None:
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        vsm = generate_virtual_site_map(tmp_path / "docs", "suffix", mgr)
        assert vsm == frozenset()


# ─── Integration tests: check_nav_contract ────────────────────────────────────


class TestNavContract:
    def test_suffix_mode_with_folder_alternate_is_error(self, tmp_path: Path) -> None:
        """/it/ is not in the VSM — no file maps to that URL → error."""
        _make_docs(tmp_path, ["index.md", "index.it.md"])
        _write_mkdocs(
            tmp_path,
            {
                "site_name": "Test",
                "plugins": [
                    {
                        "i18n": {
                            "docs_structure": "suffix",
                            "languages": [
                                {"locale": "en", "default": True, "build": True},
                                {"locale": "it", "build": True},
                            ],
                        }
                    }
                ],
                "extra": {
                    "alternate": [
                        {"name": "English", "link": "/", "lang": "en"},
                        {"name": "Italiano", "link": "/it/", "lang": "it"},
                    ]
                },
            },
        )
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = check_nav_contract(tmp_path, mgr)
        assert len(errors) == 1
        assert "extra.alternate[it]" in errors[0]
        assert "/it/" in errors[0]

    def test_suffix_mode_correct_alternate_is_ok(self, tmp_path: Path) -> None:
        """/index.it/ is in the VSM → no error."""
        _make_docs(tmp_path, ["index.md", "index.it.md"])
        _write_mkdocs(
            tmp_path,
            {
                "site_name": "Test",
                "plugins": [
                    {
                        "i18n": {
                            "docs_structure": "suffix",
                            "languages": [
                                {"locale": "en", "default": True, "build": True},
                                {"locale": "it", "build": True},
                            ],
                        }
                    }
                ],
                "extra": {
                    "alternate": [
                        {"name": "English", "link": "/", "lang": "en"},
                        {"name": "Italiano", "link": "/index.it/", "lang": "it"},
                    ]
                },
            },
        )
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = check_nav_contract(tmp_path, mgr)
        assert errors == []

    def test_suffix_mode_no_alternate_is_ok(self, tmp_path: Path) -> None:
        """No extra.alternate → nothing to validate → OK."""
        _make_docs(tmp_path, ["index.md", "index.it.md"])
        _write_mkdocs(
            tmp_path,
            {
                "site_name": "Test",
                "plugins": [
                    {
                        "i18n": {
                            "docs_structure": "suffix",
                            "languages": [
                                {"locale": "en", "default": True, "build": True},
                                {"locale": "it", "build": True},
                            ],
                        }
                    }
                ],
            },
        )
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = check_nav_contract(tmp_path, mgr)
        assert errors == []

    def test_folder_mode_with_folder_alternate_is_ok(self, tmp_path: Path) -> None:
        """folder mode: docs/it/index.md exists → /it/ is in VSM → OK."""
        _make_docs(tmp_path, ["index.md", "it/index.md"])
        _write_mkdocs(
            tmp_path,
            {
                "site_name": "Test",
                "plugins": [
                    {
                        "i18n": {
                            "docs_structure": "folder",
                            "fallback_to_default": True,
                            "languages": [
                                {"locale": "en", "default": True, "build": True},
                                {"locale": "it", "build": True},
                            ],
                        }
                    }
                ],
                "extra": {
                    "alternate": [
                        {"name": "English", "link": "/", "lang": "en"},
                        {"name": "Italiano", "link": "/it/", "lang": "it"},
                    ]
                },
            },
        )
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = check_nav_contract(tmp_path, mgr)
        assert errors == []

    def test_no_mkdocs_yml_is_ok(self, tmp_path: Path) -> None:
        """No mkdocs.yml → graceful no-op → OK."""
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = check_nav_contract(tmp_path, mgr)
        assert errors == []

    def test_multiple_locales_reports_each_invalid(self, tmp_path: Path) -> None:
        """/it/ and /fr/ not in VSM → two errors."""
        _make_docs(tmp_path, ["index.md", "index.it.md", "index.fr.md"])
        _write_mkdocs(
            tmp_path,
            {
                "site_name": "Test",
                "plugins": [
                    {
                        "i18n": {
                            "docs_structure": "suffix",
                            "languages": [
                                {"locale": "en", "default": True, "build": True},
                                {"locale": "it", "build": True},
                                {"locale": "fr", "build": True},
                            ],
                        }
                    }
                ],
                "extra": {
                    "alternate": [
                        {"name": "English", "link": "/", "lang": "en"},
                        {"name": "Italiano", "link": "/it/", "lang": "it"},
                        {"name": "Français", "link": "/fr/", "lang": "fr"},
                    ]
                },
            },
        )
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = check_nav_contract(tmp_path, mgr)
        assert len(errors) == 2
        assert any("it" in e for e in errors)
        assert any("fr" in e for e in errors)

    def test_strategy_change_folder_to_suffix_detected(self, tmp_path: Path) -> None:
        """Ghost in the Machine: config switched to suffix but alternate still
        points to /it/ (folder-mode URL). VSM has no /it/ → error caught."""
        # Only suffix-mode files on disk — no docs/it/ directory
        _make_docs(tmp_path, ["index.md", "index.it.md", "guide.md", "guide.it.md"])
        _write_mkdocs(
            tmp_path,
            {
                "site_name": "Test",
                "plugins": [
                    {
                        "i18n": {
                            "docs_structure": "suffix",  # ← changed from folder
                            "languages": [
                                {"locale": "en", "default": True, "build": True},
                                {"locale": "it", "build": True},
                            ],
                        }
                    }
                ],
                "extra": {
                    "alternate": [
                        {"name": "English", "link": "/", "lang": "en"},
                        {"name": "Italiano", "link": "/it/", "lang": "it"},  # ← stale
                    ]
                },
            },
        )
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = check_nav_contract(tmp_path, mgr)
        assert len(errors) == 1
        assert "/it/" in errors[0]


# ─── Zensical: [project.extra].alternate ──────────────────────────────────────
#
# Zensical's own official documentation (zensical.org/docs/setup/language/)
# confirms the exact same alternate-links mechanism as mkdocs-material,
# structurally identical (name/link/lang per entry), just nested under
# [project.extra] in zensical.toml instead of extra: in mkdocs.yml:
#
#   [project.extra]
#   alternate = [
#     { name = "English", link = "/en/", lang = "en" },
#     { name = "Deutsch", link = "/de/", lang = "de" },
#   ]
#
# check_nav_contract() previously hardcoded find_config_file() (mkdocs-only)
# with no engine parameter at all, so this exact class of misconfiguration
# was silently unchecked for every Zensical project. Regression coverage
# for V031_Z406_REOPEN_AS_ADAPTER_GAP.


def _write_zensical(repo: Path, extra_toml_body: str) -> None:
    """Write a minimal zensical.toml. *extra_toml_body* is appended verbatim
    under ``[project]`` -- callers supply the ``[project.extra]`` block and
    any other keys directly, since tomllib (stdlib) has no TOML writer."""
    (repo / "zensical.toml").write_text(
        f'[project]\nsite_name = "Test"\ndocs_dir = "docs"\n{extra_toml_body}\n',
        encoding="utf-8",
    )


class TestNavContractZensical:
    def test_zensical_broken_alternate_is_error(self, tmp_path: Path) -> None:
        """/it/ is not in the VSM — no file maps to that URL → error."""
        _make_docs(tmp_path, ["index.md", "index.it.md"])
        _write_zensical(
            tmp_path,
            """
[project.extra]
alternate = [
  { name = "English", link = "/", lang = "en" },
  { name = "Italiano", link = "/it/", lang = "it" },
]
""",
        )
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = check_nav_contract(tmp_path, mgr, engine="zensical")
        assert len(errors) == 1
        assert "it" in errors[0]
        assert "/it/" in errors[0]

    def test_zensical_correct_alternate_is_ok(self, tmp_path: Path) -> None:
        """/index.it/ is in the VSM (suffix mode) → no error."""
        _make_docs(tmp_path, ["index.md", "index.it.md"])
        _write_zensical(
            tmp_path,
            """
[project.extra]
alternate = [
  { name = "English", link = "/", lang = "en" },
  { name = "Italiano", link = "/index.it/", lang = "it" },
]
""",
        )
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = check_nav_contract(tmp_path, mgr, engine="zensical")
        assert errors == []

    def test_zensical_no_config_file_returns_empty(self, tmp_path: Path) -> None:
        """No zensical.toml present -> no violations, no crash."""
        _make_docs(tmp_path, ["index.md"])
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = check_nav_contract(tmp_path, mgr, engine="zensical")
        assert errors == []

    def test_default_engine_still_reads_mkdocs(self, tmp_path: Path) -> None:
        """engine defaults to "mkdocs" -- existing callers/tests are unaffected."""
        _make_docs(tmp_path, ["index.md", "index.it.md"])
        _write_mkdocs(
            tmp_path,
            {
                "site_name": "Test",
                "extra": {
                    "alternate": [
                        {"name": "Italiano", "link": "/it/", "lang": "it"},
                    ]
                },
            },
        )
        config = ZenzicConfig()
        mgr = make_mgr(config, repo_root=tmp_path)
        errors = check_nav_contract(tmp_path, mgr)
        assert len(errors) == 1
        assert "mkdocs.yml" in errors[0]
