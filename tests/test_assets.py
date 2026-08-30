# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for unused assets scanning."""

from __future__ import annotations

from pathlib import Path

from _helpers import make_mgr

from zenzic.core.scanner import find_unused_assets
from zenzic.models.config import ZenzicConfig


def test_find_unused_assets(tmp_path: Path) -> None:
    repo = tmp_path / "my_repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)

    # Create some assets
    assets_dir = docs / "assets"
    assets_dir.mkdir()
    (assets_dir / "used.png").touch()
    (assets_dir / "unused.png").touch()
    (assets_dir / "used_img_tag.svg").touch()

    # Excluded formats
    (assets_dir / "style.css").touch()
    (assets_dir / "script.js").touch()

    # Create md files referencing them
    md1 = docs / "index.md"
    md1.write_text("Here is an image: ![Alt text](assets/used.png)")

    md2 = docs / "nested" / "page.md"
    md2.parent.mkdir()
    md2.write_text("Here is another: <img src='../assets/used_img_tag.svg' />")

    # Create an external link that shouldn't be matched
    md3 = docs / "external.md"
    md3.write_text("External: ![Alt](https://example.com/image.png)")

    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=repo)
    unused = find_unused_assets(docs, mgr, config=config)

    assert len(unused) == 1
    assert unused[0].name == "unused.png"


def test_frontmatter_image_reference_not_flagged_unused(tmp_path: Path) -> None:
    repo = tmp_path / "my_repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)

    assets_dir = docs / "assets" / "social"
    assets_dir.mkdir(parents=True)
    (assets_dir / "card.png").touch()

    md = docs / "post.md"
    md.write_text(
        "---\n"
        "title: A post\n"
        "image: assets/social/card.png\n"
        "---\n\n"
        "Body text with no markdown link to the card image.\n"
    )

    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=repo)
    unused = find_unused_assets(docs, mgr, config=config)

    assert unused == []


def test_excluded_assets_not_reported(tmp_path: Path) -> None:
    repo = tmp_path / "my_repo"
    docs = repo / "docs"
    (docs / "assets").mkdir(parents=True)

    (docs / "assets" / "favicon.svg").touch()
    (docs / "assets" / "logo.png").touch()
    (docs / "assets" / "used.png").touch()

    (docs / "index.md").write_text("![img](assets/used.png)")

    config = ZenzicConfig(excluded_assets=["assets/favicon.svg", "assets/logo.png"])
    mgr = make_mgr(config, repo_root=repo)
    unused = find_unused_assets(docs, mgr, config=config)

    names = [p.name for p in unused]
    assert "favicon.svg" not in names
    assert "logo.png" not in names
    assert "used.png" not in names


def test_excluded_assets_non_excluded_still_reported(tmp_path: Path) -> None:
    repo = tmp_path / "my_repo"
    docs = repo / "docs"
    (docs / "assets").mkdir(parents=True)

    (docs / "assets" / "favicon.svg").touch()
    (docs / "assets" / "orphan.png").touch()

    (docs / "index.md").write_text("No images here.")

    config = ZenzicConfig(excluded_assets=["assets/favicon.svg"])
    mgr = make_mgr(config, repo_root=repo)
    unused = find_unused_assets(docs, mgr, config=config)

    names = [p.name for p in unused]
    assert "favicon.svg" not in names
    assert "orphan.png" in names


def test_excluded_assets_empty_list_behavior(tmp_path: Path) -> None:
    repo = tmp_path / "my_repo"
    docs = repo / "docs"
    (docs / "assets").mkdir(parents=True)

    (docs / "assets" / "logo.png").touch()
    (docs / "index.md").write_text("No images here.")

    config = ZenzicConfig(excluded_assets=[])
    mgr = make_mgr(config, repo_root=repo)
    unused = find_unused_assets(docs, mgr, config=config)

    assert any(p.name == "logo.png" for p in unused)


def test_excluded_assets_leading_slash_stripped(tmp_path: Path) -> None:
    repo = tmp_path / "my_repo"
    docs = repo / "docs"
    (docs / "assets").mkdir(parents=True)

    (docs / "assets" / "favicon.svg").touch()
    (docs / "index.md").write_text("No images here.")

    config = ZenzicConfig(excluded_assets=["/assets/favicon.svg"])
    mgr = make_mgr(config, repo_root=repo)
    unused = find_unused_assets(docs, mgr, config=config)

    assert not any(p.name == "favicon.svg" for p in unused)


def test_excluded_assets_glob_pattern(tmp_path: Path) -> None:
    """Glob patterns (fnmatch) in excluded_assets suppress matching files."""
    repo = tmp_path / "my_repo"
    docs = repo / "docs"
    (docs / "community").mkdir(parents=True)
    (docs / "guides").mkdir(parents=True)

    (docs / "community" / "_category_.json").touch()
    (docs / "guides" / "_category_.json").touch()
    (docs / "guides" / "orphan.png").touch()

    (docs / "index.md").write_text("No images here.")

    config = ZenzicConfig(excluded_assets=["**/_category_.json"])
    mgr = make_mgr(config, repo_root=repo)
    unused = find_unused_assets(docs, mgr, config=config)

    names = [p.name for p in unused]
    assert "_category_.json" not in names
    assert "orphan.png" in names


def test_excluded_assets_wildcard_pattern(tmp_path: Path) -> None:
    """Wildcard patterns exclude all matching assets in a directory."""
    repo = tmp_path / "my_repo"
    docs = repo / "docs"
    brand = docs / "assets" / "brand"
    brand.mkdir(parents=True)

    (brand / "logo.svg").touch()
    (brand / "icon.svg").touch()
    (docs / "assets" / "screenshot.png").touch()
    (docs / "index.md").write_text("No images here.")

    config = ZenzicConfig(excluded_assets=["assets/brand/*"])
    mgr = make_mgr(config, repo_root=repo)
    unused = find_unused_assets(docs, mgr, config=config)

    names = [p.name for p in unused]
    assert "logo.svg" not in names
    assert "icon.svg" not in names
    assert "screenshot.png" in names


def test_z405_respects_exclusions_and_dotfiles(tmp_path: Path) -> None:
    """Verify VCS-ignored files and dotfiles/dotdirectories are skipped by Z405, but security scans remain active."""
    from zenzic.core.scanner import ReferenceScanner

    repo = tmp_path / "my_repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)

    # 1. Create a dotfile in docs that is unreferenced
    (docs / ".config_pubblica").touch()

    # 2. Create a file inside a dotdirectory
    dotdir = docs / ".github" / "workflows"
    dotdir.mkdir(parents=True)
    (dotdir / "ci.yml").touch()

    # 3. Create a gitignored file in docs (VCS ignore simulation)
    (repo / ".gitignore").write_text(".clinerules\n")
    (docs / ".clinerules").touch()

    # 4. Create an unreferenced normal asset that SHOULD be flagged by Z405
    (docs / "orphan.png").touch()

    # 5. Create a dotfile `.env` that contains an OpenAI secret
    env_file = docs / ".env"
    env_file.write_text("OPENAI_KEY = sk-" + "A" * 48 + "\n")

    # Run find_unused_assets to verify Z405 ignores dotfiles and gitignored files
    config = ZenzicConfig(respect_vcs_ignore=True)
    mgr = make_mgr(config, repo_root=repo, docs_root=docs)
    unused = find_unused_assets(docs, mgr, config=config)

    unused_names = [p.as_posix() for p in unused]
    assert "orphan.png" in unused_names
    assert ".config_pubblica" not in unused_names
    assert ".github/workflows/ci.yml" not in unused_names
    assert ".clinerules" not in unused_names
    assert ".env" not in unused_names

    # Verify that Z201 is active on the .env file when scanned via ReferenceScanner
    scanner = ReferenceScanner(env_file, config)
    findings = [data for _, evt, data in scanner.harvest() if evt == "SECRET"]
    assert len(findings) == 1
    assert findings[0].secret_type == "openai-api-key"

def test_code_asset_suffixes_exempts_mts_and_cts(tmp_path: Path) -> None:
    """TypeScript's explicit-module-type extensions (.mts/.cts) are source code,
    not documentation assets — same exemption class as the already-covered .mjs/.cjs
    (Discovered via V031_CI_COVERAGE_GATES_IMPLEMENTATION: a real standalone-mode repo's
    vitest.config.mts was false-flagged as Z405 UNUSED_ASSET before this fix)."""
    repo = tmp_path / "my_repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)

    (docs / "vitest.config.mts").touch()
    (docs / "build.cts").touch()
    (docs / "unused.png").touch()

    config = ZenzicConfig()
    mgr = make_mgr(config, repo_root=repo)
    unused = find_unused_assets(docs, mgr, config=config)

    unused_names = {p.name for p in unused}
    assert "vitest.config.mts" not in unused_names
    assert "build.cts" not in unused_names
    assert "unused.png" in unused_names
