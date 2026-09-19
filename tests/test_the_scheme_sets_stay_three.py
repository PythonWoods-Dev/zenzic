# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The three scheme sets must stay three, and their differences must be deliberate.

D4. Six hardcoded lists once answered "is this URL external?", and they already
disagreed -- `xmpp:` against `xmpp://`, `ftp:` present in one and absent in three,
`mailto:` missing from five. One was dead while looking authoritative and has been
removed. What remains is three sets that are **not** duplicates and must not be
collapsed, because each serves a different tier:

* ``NON_NAVIGABLE_SCHEMES`` -- does this URL address a page in this site?
* ``LINK_BYPASS_SCHEMES``   -- should the resolver try to turn it into a route?
* ``SECURITY_BYPASS_SCHEMES`` -- should the Z202/Z203 loop stop looking at it?

The third is the reason for the arrangement: **a scheme added to it stops
reaching the path-traversal gate**. Merging the three would mean that a widening
made for resolution correctness -- adding `ftp:` so the resolver stops inventing
a route from `ftp://example.com/f.txt` -- silently also removed a security check.

So this test asserts the *relationship*, not sameness. A deliberate divergence is
a one-line edit here, recorded with its reason; an accidental one is a failure.
"""

from __future__ import annotations

from zenzic.core.validator import (
    LINK_BYPASS_SCHEMES,
    NON_NAVIGABLE_SCHEMES,
    SECURITY_BYPASS_SCHEMES,
)


#: Measured 2026-09-19 by calling `resolve_link_to_canonical` on each scheme:
#: every one of these returned ``None`` (correctly bypassed) except the two
#: `ftp:` spellings, which resolved to site paths `/f.txt` and
#: `/example.com/f.txt`.
_SHARED = frozenset({"mailto:", "tel:", "javascript:", "data:", "irc:", "xmpp:"})


def test_every_set_carries_the_shared_core() -> None:
    for name, group in (
        ("NON_NAVIGABLE_SCHEMES", NON_NAVIGABLE_SCHEMES),
        ("LINK_BYPASS_SCHEMES", LINK_BYPASS_SCHEMES),
        ("SECURITY_BYPASS_SCHEMES", SECURITY_BYPASS_SCHEMES),
    ):
        missing = _SHARED - set(group)
        assert not missing, f"{name} lost {sorted(missing)} from the shared core"


def test_only_the_navigability_set_carries_ftp() -> None:
    """The measured asymmetry, pinned so it cannot change by accident.

    `ftp:` belongs to "does not address a page here" and is absent from the two
    bypass sets. Adding it to the resolver's set is a correctness change to
    resolution; adding it to the security set removes a check. Either is
    allowed, neither silently.
    """
    assert "ftp:" in NON_NAVIGABLE_SCHEMES
    assert "ftp:" not in LINK_BYPASS_SCHEMES
    assert "ftp:" not in SECURITY_BYPASS_SCHEMES


def test_only_the_bypass_sets_carry_http() -> None:
    """`http://`/`https://` are external links, tested by the pass that probes them."""
    for scheme in ("http://", "https://"):
        assert scheme not in NON_NAVIGABLE_SCHEMES
        assert scheme in LINK_BYPASS_SCHEMES
        assert scheme in SECURITY_BYPASS_SCHEMES


def test_the_security_set_is_never_wider_than_the_resolver_set() -> None:
    """The invariant that makes the split safe rather than merely tidy.

    The security set may be *narrower* -- a narrower bypass means more links
    reach the traversal gate, which is protective. It must never be wider,
    because that would silence a check the resolver does not even perform.
    """
    extra = set(SECURITY_BYPASS_SCHEMES) - set(LINK_BYPASS_SCHEMES)
    assert not extra, (
        f"the security bypass is wider than the resolver's by {sorted(extra)}; "
        "every scheme added there stops reaching the path-traversal gate"
    )


def test_no_scheme_is_spelled_two_ways_within_a_set() -> None:
    """The original defect: one list spelled it `xmpp://` where three said `xmpp:`."""
    for name, group in (
        ("NON_NAVIGABLE_SCHEMES", NON_NAVIGABLE_SCHEMES),
        ("LINK_BYPASS_SCHEMES", LINK_BYPASS_SCHEMES),
        ("SECURITY_BYPASS_SCHEMES", SECURITY_BYPASS_SCHEMES),
    ):
        bare = {s.rstrip("/") for s in group}
        assert len(bare) == len(set(group)), f"{name} spells one scheme two ways: {sorted(group)}"
