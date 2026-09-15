# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Z503 must not fire on a snippet demonstrating syntax, and must still fire on a broken one."""

from __future__ import annotations

from pathlib import Path

from zenzic.core.validator import check_snippet_content


P = Path("t.md")


def _codes(md: str) -> list[str]:
    return [e.message for e in check_snippet_content(md, P)]


# --- Population A: placeholder KEY in TOML (didactic) -> silent
def test_toml_placeholder_key_is_silent() -> None:
    md = '```toml\n[project.theme.icon.admonition]\n<type> = "<icon>"\n```\n'
    assert _codes(md) == [], _codes(md)


# --- Population A limit: placeholder in a VALUE still validated
def test_toml_placeholder_in_value_still_parses() -> None:
    md = '```toml\n[project]\nlink = "mailto:<email-address>"\n```\n'
    assert _codes(md) == [], _codes(md)


# --- Population A opposite direction: a genuinely malformed TOML still fires
def test_genuinely_broken_toml_still_fires() -> None:
    md = "```toml\n[project]\nkey = \n```\n"
    assert len(_codes(md)) == 1, _codes(md)


# --- Population B: body that opens a fence (didactic) -> silent
def test_nested_fence_body_is_silent() -> None:
    md = "````yaml\n``` { .yaml .copy }\n# Code block content\n```\n````\n"
    assert _codes(md) == [], _codes(md)


# --- Population B opposite direction: genuinely broken YAML still fires
def test_genuinely_broken_yaml_still_fires() -> None:
    md = "```yaml\nfoo: [unclosed\nbar: 1\n```\n"
    assert len(_codes(md)) == 1, _codes(md)
