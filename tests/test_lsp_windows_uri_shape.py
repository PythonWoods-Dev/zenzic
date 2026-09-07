# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""VS Code encodes a Windows drive colon: ``file:///d%3A/...``, not ``file:///D:/...``.

Python's ``Path.as_uri()`` -- which every other LSP test here uses -- never
produces the encoded form, so the server's URI-to-path conversion had zero
coverage of the shape a real client sends. On Windows, ``url2pathname`` splits
on the colon *before* unquoting, so the encoded colon hides the drive and the
result is a bogus rooted path. Everything built from ``rootUri`` -- the docs
root, the site map, broken-link diagnostics, rename repairs -- silently came
out empty for every Windows user, while text-only features kept working.

Surfaced by the VS Code extension's first Windows CI run of its extension-host
suite: six failures, all site-map-backed, save-hook green.
"""

from __future__ import annotations

import sys

import pytest

from zenzic.lsp.server import uri_to_path


@pytest.mark.parametrize(
    ("encoded", "plain"),
    [
        ("file:///d%3A/a/ws/docs/b.md", "file:///D:/a/ws/docs/b.md"),
        (
            "file:///c%3A/Users/r/AppData/Local/Temp/x/docs/a.md",
            "file:///C:/Users/r/AppData/Local/Temp/x/docs/a.md",
        ),
    ],
)
def test_encoded_drive_colon_converts_like_the_plain_form(encoded: str, plain: str) -> None:
    """The two spellings name the same file and must yield the same path."""
    assert uri_to_path(encoded) == uri_to_path(plain)


@pytest.mark.skipif(sys.platform != "win32", reason="drive letters exist only on Windows")
def test_encoded_drive_colon_yields_a_drive_on_windows() -> None:
    p = uri_to_path("file:///d%3A/a/ws/docs/b.md")
    assert p.drive.upper() == "D:", f"no drive recovered: {p!r}"
    assert p.as_posix().lower().endswith("/a/ws/docs/b.md")


def test_percent_encoded_space_is_still_decoded_once() -> None:
    """Fixing the colon must not double-decode ordinary escapes."""
    p = uri_to_path("file:///tmp/my%20docs/a%2520b.md")
    assert p.name == "a%20b.md" and "my docs" in p.as_posix()


def test_url2pathname_is_called_from_exactly_one_module() -> None:
    """Structural: three private copies of the conversion once existed and all
    three carried the same defect. A fourth copy must not be able to appear."""
    from pathlib import Path as _P

    src = _P(__file__).resolve().parents[1] / "src" / "zenzic"
    callers = sorted(
        str(p.relative_to(src))
        for p in src.rglob("*.py")
        if "url2pathname(" in p.read_text(encoding="utf-8")
    )
    assert callers == ["models/vsm.py"], callers


def test_the_engine_and_the_server_use_the_same_conversion() -> None:
    from zenzic.core import incremental
    from zenzic.lsp import server
    from zenzic.models import vsm

    u = "file:///d%3A/a/ws/docs/b.md"
    assert incremental._uri_to_path(u) == vsm.uri_to_path(u) == server.uri_to_path(u)
