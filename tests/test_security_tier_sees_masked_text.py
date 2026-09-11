# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The security tier must not inherit the quality tier's masking.

Masking answers a quality question -- "is this text content?" -- so a link in a
comment is not reported broken.  The security tier asks "does this document
contain a forbidden scheme or a traversal?", and for that the whole document is
in scope: a payload is no less real for sitting in a comment.  Consulting the
quality mask here made "the scanner did not look there" a suppression mechanism
for codes ``codes.py`` declares non-suppressible.

A *closed* fence is the one exception -- see PolyglotExtractor._mask_security_view.
"""

from __future__ import annotations

import pytest

from zenzic.core.validator import PolyglotExtractor


JS = "javascript:alert(1)"

UNMASKED = [
    pytest.param(f"Cost is $5 - [c]({JS}) - or $10.", id="inline-math-span"),
    pytest.param(f"```python\nx = 1\n\n[c]({JS})\n", id="unterminated-fence"),
    pytest.param(f"<!-- [c]({JS}) -->", id="html-comment"),
    pytest.param(f"{{/* [c]({JS}) */}}", id="mdx-comment"),
    pytest.param(f"[c]({JS})", id="plain-positive-control"),
]


@pytest.mark.parametrize("text", UNMASKED)
def test_security_view_sees_the_payload(text: str) -> None:
    """A forbidden scheme reaches the security tier regardless of masking context."""
    urls = [link.url for link in PolyglotExtractor().extract_security_links(text)]
    assert any(u.startswith("javascript:") for u in urls), (
        f"masking hid a forbidden scheme from the security tier: {text!r} -> {urls}"
    )


def test_closed_fence_stays_masked() -> None:
    """The accepted residual risk, pinned so it cannot change silently.

    Zenzic's own Z203/Z205 rule pages teach those rules by showing the payloads
    inside closed fences.  Z205 is exit 2 and non-suppressible, so unmasking a
    closed fence would make Zenzic's own documentation unfixable.
    """
    text = f'```html\n<a href="{JS}">x</a>\n```'
    urls = [link.url for link in PolyglotExtractor().extract_security_links(text)]
    assert not any(u.startswith("javascript:") for u in urls)


@pytest.mark.parametrize("text", UNMASKED[:4])
def test_quality_tier_still_masks(text: str) -> None:
    """The other direction: the quality extractor must NOT have moved."""
    urls = [link.url for link in PolyglotExtractor().extract_all_links(text)]
    assert not any(u.startswith("javascript:") for u in urls), (
        f"quality tier regressed -- it should still mask {text!r}"
    )


# ── A Markdown link inside a JSX string attribute is not a link ───────────────
#
# The security tier deliberately sees more than the quality tier: a payload is
# no less real for sitting in a comment. But `<Callout text="see [p](…)" />` is
# a *string prop*, and Markdown link syntax inside one renders as literal text --
# MDX does not parse it, no anchor reaches the page, and no href exists. The
# quality tier has masked it since the extraction fix; the security tier did not,
# so a prop string produced Z202 and, once the filesystem downgrade was correctly
# removed, Z203 -- exit 3, non-suppressible, on text that is not a link.
#
# The mask is safe here precisely because of what it does NOT match: it blanks
# only an attribute value containing `[...](...)`. A plain URL in a prop --
# `<Callout to="javascript:alert(1)" />`, the case that genuinely can render a
# link through a component -- is left untouched and still reaches the tier.

TRAVERSAL = "../../../../etc/passwd"

PROP_STRING_NOT_A_LINK = [
    pytest.param(f'<Callout text="see [p]({TRAVERSAL}) for details" />', id="traversal-in-prop"),
    pytest.param(f'<Callout text="see [c]({JS}) here" />', id="scheme-in-prop"),
    pytest.param(f'<a href="./real.md" title="see [c]({JS})">x</a>', id="markdown-link-in-title"),
]


@pytest.mark.parametrize("text", PROP_STRING_NOT_A_LINK)
def test_markdown_link_in_a_prop_string_is_not_a_security_finding(text: str) -> None:
    """A prop string renders no anchor, so it carries no payload to report."""
    urls = [link.url for link in PolyglotExtractor().extract_security_links(text)]
    assert not any(u.startswith("javascript:") or TRAVERSAL in u for u in urls), (
        f"prop string produced a security-tier link: {text!r} -> {urls}"
    )


REAL_VECTORS = [
    pytest.param(f'<a href="{JS}">x</a>', "javascript:", id="scheme-in-real-href"),
    pytest.param(f'<a href="{TRAVERSAL}">x</a>', TRAVERSAL, id="traversal-in-real-href"),
    pytest.param(f"[c]({JS})", "javascript:", id="plain-markdown-link"),
    pytest.param(f"[p]({TRAVERSAL})", TRAVERSAL, id="plain-markdown-traversal"),
]


@pytest.mark.parametrize("text,needle", REAL_VECTORS)
def test_a_real_payload_still_reaches_the_security_tier(text: str, needle: str) -> None:
    """The other direction, and the reason the mask is scoped to link syntax.

    Without these the test above would also pass if the mask blanked every
    attribute value, or if extraction were removed outright.

    `<Callout to="javascript:...">` is deliberately not among these: the tag gate
    is `a|img|link`, so a component prop never reaches the extractor at all. That
    is the separate, still-open `<Link>`/`<Anchor>` scope question -- this mask
    neither loses it nor grants it.
    """
    urls = [link.url for link in PolyglotExtractor().extract_security_links(text)]
    assert any(needle in u for u in urls), f"lost a real payload: {text!r} -> {urls}"
