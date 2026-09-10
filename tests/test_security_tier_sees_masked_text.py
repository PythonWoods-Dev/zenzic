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
