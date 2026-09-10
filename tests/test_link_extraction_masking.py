# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Links inside comments and JSX attributes are not links.

`_extract_inline_links_with_lines` feeds the Z101 rule. Its docstring claimed it
skips "fenced code blocks, inline code spans, and math blocks"; it masked math
and fences and inline code, and nothing else. A Markdown link written inside an
HTML comment, an MDX comment, or a JSX string attribute was therefore extracted
and reported as a broken link.

Two of the three reach plain `.md`, not only `.mdx`: `<!-- ... -->` is ordinary
Markdown, and every commented-out link in any document was a false Z101.

`PolyglotExtractor.extract_all_links` already handled all of this correctly --
the defect was one code path not using the masking that already existed, which
is why the fix routes rather than rewrites a regex.

Every case is asserted in BOTH directions. A fix that masked too greedily would
silence the false positive and the genuine link in the same file, and a
one-directional test would pass on it.
"""

from __future__ import annotations

from zenzic.core.rules import _extract_inline_links_with_lines as extract


GENUINE = "A [genuine](./real-missing.md) link."


def _urls(text: str) -> list[str]:
    return [u for u, _lineno, _raw in extract(text)]


class TestCommentsAreNotLinks:
    def test_html_comment_link_is_not_extracted(self) -> None:
        """Plain Markdown: a commented-out link is not a link."""
        text = f"<!-- An [old link](./ghost.md) here -->\n{GENUINE}\n"
        urls = _urls(text)
        assert "./ghost.md" not in urls, urls

    def test_html_comment_does_not_swallow_a_genuine_link(self) -> None:
        text = f"<!-- An [old link](./ghost.md) here -->\n{GENUINE}\n"
        assert "./real-missing.md" in _urls(text)

    def test_mdx_comment_link_is_not_extracted(self) -> None:
        text = f"{{/* A [commented link](./ghost.md) */}}\n{GENUINE}\n"
        assert "./ghost.md" not in _urls(text)

    def test_mdx_comment_does_not_swallow_a_genuine_link(self) -> None:
        text = f"{{/* A [commented link](./ghost.md) */}}\n{GENUINE}\n"
        assert "./real-missing.md" in _urls(text)

    def test_multiline_html_comment(self) -> None:
        text = f"<!--\n  A [link](./ghost.md)\n-->\n{GENUINE}\n"
        urls = _urls(text)
        assert "./ghost.md" not in urls, urls
        assert "./real-missing.md" in urls


class TestJsxAttributesAreNotLinks:
    def test_jsx_string_attribute_link_is_not_extracted(self) -> None:
        text = f'<Foo label="see [attr link](./ghost2.md) here" />\n{GENUINE}\n'
        assert "./ghost2.md" not in _urls(text)

    def test_jsx_attribute_does_not_swallow_a_genuine_link(self) -> None:
        text = f'<Foo label="see [attr link](./ghost2.md) here" />\n{GENUINE}\n'
        assert "./real-missing.md" in _urls(text)


class TestNothingElseRegressed:
    def test_a_plain_link_is_still_extracted(self) -> None:
        assert "./real-missing.md" in _urls(GENUINE)

    def test_a_real_html_anchor_is_still_extracted(self) -> None:
        assert "./page.md" in _urls('<a href="./page.md">x</a>\n')

    def test_inline_code_still_masked(self) -> None:
        assert "./c.md" not in _urls("Inline `[x](./c.md)` span.\n")

    def test_fenced_block_still_skipped(self) -> None:
        assert "./f.md" not in _urls("```\n[x](./f.md)\n```\n")

    def test_line_numbers_survive_masking(self) -> None:
        """Masking must be length/line preserving -- carets depend on it."""
        text = f"<!-- [g](./ghost.md) -->\n\n{GENUINE}\n"
        found = [(u, n) for u, n, _ in extract(text)]
        assert ("./real-missing.md", 3) in found, found
