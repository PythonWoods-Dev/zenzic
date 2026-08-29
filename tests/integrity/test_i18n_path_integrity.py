# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""i18n Path Integrity checks (Direttiva CEO 124/125).

Four invariants the multi-root scanner must enforce simultaneously for files
living in an injected locale root (a directory outside ``docs_root``, mapped
in via the ``locale_roots`` parameter of :func:`validate_links_structured` —
the same mechanism a real adapter's ``get_locale_source_roots()`` would use).
The ``i18n/<locale>/docusaurus-plugin-content-docs/current/`` shape is used
as the test fixture purely because it is a well-known, realistic example of
this directory convention — it does not require or assume the (removed)
Docusaurus engine adapter itself; ``locale_roots`` is injected directly here,
bypassing adapter resolution entirely.

  INT-001  Cross-locale relative links (i18n/it/ → i18n/it/) are PASS.
           A locale file linking to its sibling translation file must not be
           treated as a path-traversal attack merely because the locale root
           lives outside docs_root.

  INT-002  A locale file linking to ../../../../etc/passwd is FATAL.
           Admitting locale roots must never disable security: targets that
           resolve outside every authorised root still trigger Z203
           (PATH_TRAVERSAL_FATAL, Exit 3).

  INT-003  A same-page anchor mismatch inside a locale file is ERROR (Z102).

  INT-004  ``@site/static/`` assets should resolve correctly from locale
           files using repo_root-relative asset existence, per this file's
           original docstring claim. **Confirmed BROKEN as of this test
           (2026-08-29)** — see the `xfail`-marked test below and
           `.claude/state/03-priority-table.md` for the live reproduction
           and disposition. Not fixed here per this directive's explicit
           constraint: a confirmed live gap in security-adjacent logic is
           not fixed without an explicit Tech Lead sign-off.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _helpers import make_mgr

from zenzic.core.validator import LinkError, validate_links_structured
from zenzic.models.config import BuildContext, ZenzicConfig


def _locale_root(tmp_path: Path, locale: str = "it") -> Path:
    """Return a locale source root using the Docusaurus i18n directory shape
    (a well-known, realistic example of this convention — not a dependency
    on the removed Docusaurus adapter) and create it.
    """
    root = tmp_path / "i18n" / locale / "docusaurus-plugin-content-docs" / "current"
    root.mkdir(parents=True)
    return root


def _run(tmp_path: Path, locale_root: Path, locale: str = "it") -> list[LinkError]:
    """Run validate_links_structured with a single locale root injected directly."""
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    if not (docs / "index.md").exists():
        (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    config = ZenzicConfig(build_context=BuildContext(engine="standalone", locales=[locale]))
    mgr = make_mgr(config, repo_root=tmp_path)
    return validate_links_structured(
        docs, mgr, repo_root=tmp_path, config=config, locale_roots=[(locale_root, locale)]
    )


def test_int_001_cross_locale_sibling_link_passes(tmp_path: Path) -> None:
    """A locale file linking to its sibling translation must not be flagged."""
    root = _locale_root(tmp_path)
    (root / "page.md").write_text("# Pagina\n\n[Altra pagina](altra.md)\n", encoding="utf-8")
    (root / "altra.md").write_text("# Altra\n", encoding="utf-8")

    errors = _run(tmp_path, root)

    assert errors == []


def test_int_002_locale_file_path_traversal_is_fatal(tmp_path: Path) -> None:
    """A locale file linking outside every authorised root must trigger Z203."""
    root = _locale_root(tmp_path)
    (root / "page.md").write_text(
        "# Pagina\n\n[Escape](../../../../etc/passwd)\n", encoding="utf-8"
    )

    errors = _run(tmp_path, root)

    assert len(errors) == 1
    assert errors[0].error_type == "Z203"


def test_int_003_locale_file_same_page_anchor_mismatch_is_error(tmp_path: Path) -> None:
    """A locale file's own broken same-page anchor must be flagged as Z102."""
    root = _locale_root(tmp_path)
    (root / "page.md").write_text(
        "# Pagina\n\n[Vai](#sezione-inesistente)\n", encoding="utf-8"
    )

    errors = _run(tmp_path, root)

    assert len(errors) == 1
    assert errors[0].error_type == "Z102"


@pytest.mark.xfail(
    reason=(
        "INT-004: confirmed live gap, not fixed per directive constraint. "
        "A @site/static/ asset that genuinely exists at repo_root/static/ is "
        "still reported Z104 FILE_NOT_FOUND, from both locale and non-locale "
        "files alike (reproduced without any locale_roots involvement too — "
        "this is not locale-specific). See 03-priority-table.md."
    ),
    strict=True,
)
def test_int_004_site_static_asset_resolves_from_locale_file(tmp_path: Path) -> None:
    """A @site/static/ asset that exists at repo_root should not be Z104."""
    root = _locale_root(tmp_path)
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "logo.png").write_bytes(b"fake-png-bytes")
    (root / "page.md").write_text("# Pagina\n\n![Logo](@site/static/logo.png)\n", encoding="utf-8")

    errors = _run(tmp_path, root)

    assert errors == []
