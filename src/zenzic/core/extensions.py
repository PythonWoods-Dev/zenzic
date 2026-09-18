# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""What each Markdown extension brings, and which ones a project has enabled.

THE OWNERSHIP THIS MODULE ESTABLISHES
-------------------------------------
The core owns the mapping from **extension to construct**: `admonition` brings
``!!!``, `pymdownx.details` brings ``???`` and ``???+``, `pymdownx.tabbed`
brings ``=== "Tab"``, `def_list` brings ``:`` followed by spaces. Those are
facts about Markdown syntax, which is what the core exists to know.

The adapter owns **which extensions are enabled**, read from the project's own
configuration. That is a fact about the project, and only the project knows it.

WHY NOT THE OTHER WAY ROUND
---------------------------
An earlier design had adapters declaring markers. It was wrong, and the
measurement said so: MkDocs does not define ``!!!``, it *enables* it, and only
when the project lists `admonition` in ``markdown_extensions``. An adapter
declaring the marker would be declaring on behalf of an extension it did not
author, and would be wrong for a MkDocs project that enables none.

WHY THIS IS NOT IN codes.py
---------------------------
That registry describes what the engine *reports*. This describes what Markdown
*means*. Joining them because both are tables would merge two different
questions.

HOW THE LIST WAS FOUND, AND WHY IT IS INCOMPLETE
------------------------------------------------
Empirically, in five iterations on two corpora — list items, then ``=== "Tab"``
tabs, then nested markers, then collapsible ``???+``, then definition lists.
Never by reading: there is no specification of these constructs, because none
of them is CommonMark.

**So this list is known to be incomplete**, and the incompleteness now lives
where it can be stated per extension rather than guessed. What it cannot cover:
a third-party extension (`zensical.extensions.*` in the foreign corpus) whose
constructs the core has never seen.

**The risk is asymmetric in the useful direction.** A missing marker makes the
tracker treat container content as indented code, which *removes* findings —
and a corpus measurement finds that, as it found these five. A spurious marker
would add findings, which nobody reports.

OPTIONS, AND WHY THEY ARE CARRIED
---------------------------------
The container vocabulary keys on the extension **name**: measured 2026-09-18,
`pymdownx.tabbed` is the only relevant extension carrying options in either
corpus, and its ``alternate_style`` does not change the marker — both corpora
enable it and both write ``===``.

But ``combine_header_slug`` *does* change what that extension produces: it mints
the anchors `Z102` reports missing. So the options travel with the name, because
one consumer needs them even though the container vocabulary does not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from zenzic.core import regex as re


if TYPE_CHECKING:
    from zenzic.core.regex import RegexPattern

#: Marker patterns each extension introduces, as alternatives for the container
#: regex. Each entry was verified against a corpus that enables the extension
#: and writes the construct -- never inferred from the extension's name.
#:
#: Leading whitespace is unbounded on purpose: containers nest, and a nested
#: marker sits four or more columns in. The "up to three spaces" of CommonMark
#: is measured from the containing block, not from column zero.
BLOCK_CONSTRUCTS: dict[str, tuple[str, ...]] = {
    # Python-Markdown core. `!!! note` opens a block whose content is indented.
    "admonition": (r"^[ \t]*!!!\s",),
    # pymdownx.details -- the collapsible form, and its expanded `???+`.
    "pymdownx.details": (r"^[ \t]*\?\?\?\+?\s",),
    # pymdownx.tabbed -- `=== "Tab"`. Content, not a bare `===`, which is a
    # setext H1 underline; the two share a prefix and the distinction is the
    # text after the marker.
    "pymdownx.tabbed": (r"^[ \t]*={3,}\s+\S",),
    # Python-Markdown `def_list` -- `:` followed by spaces opens the definition
    # body, indented.
    "def_list": (r"^[ \t]*:[ \t]+\S",),
}

#: List items are CommonMark itself (§5.2), not an extension, so they are always
#: present regardless of what a project enables.
CORE_BLOCK_CONSTRUCTS: tuple[str, ...] = (r"^[ \t]*(?:[-+*]|\d{1,9}[.)])\s",)

#: What an engine assumes when it has no configuration to read -- `standalone`
#: and `prebuilt`. **Not emptiness**: measured 2026-09-18, an empty vocabulary
#: classifies 1,112 lines of our own corpus and 1,068 of `zensical/docs` as
#: indented code, skipped by every consumer that opts into `in_indented_code`.
#: That is the opposite defect, an order of magnitude larger than the one the
#: tracker exists to fix.
#:
#: The four below are the argument: both corpora measured enable all four, they
#: are what Material-flavoured Markdown uses, and a project writing plain
#: CommonMark has none of these markers in its text — so assuming them costs it
#: nothing, while assuming none costs an admonition-using project everything.
DEFAULT_EXTENSIONS: frozenset[str] = frozenset(BLOCK_CONSTRUCTS)


@dataclass(frozen=True, slots=True)
class EnabledExtensions:
    """What a project enables, as the adapter read it.

    ``names`` answers the container question; ``options`` carries the rest,
    because the anchor-slug rules need `pymdownx.tabbed`'s settings even though
    the container vocabulary does not.
    """

    names: frozenset[str] = field(default_factory=frozenset)
    options: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Entries the loader handed over in a shape with no readable name. Counted
    #: rather than dropped: an enabled extension the contract cannot see is
    #: exactly the condition this number exists to surface.
    unreadable: int = 0

    @classmethod
    def from_declaration(cls, declared: object) -> EnabledExtensions:
        """Read MkDocs' ``markdown_extensions`` shape: strings and 1-key maps.

        Both real corpora mix the two forms. Anything else is ignored rather
        than guessed at -- an unreadable entry must not silently become an
        enabled extension.
        """
        names: set[str] = set()
        options: dict[str, dict[str, Any]] = {}
        unreadable = 0
        if not isinstance(declared, list):
            return cls(frozenset(), {}, 0)
        for entry in declared:
            if isinstance(entry, str):
                # A `!!python/name:` entry arrives here as the empty string:
                # the permissive loader neither resolves the reference nor
                # keeps its text. Measured 2026-09-18. Such an extension is
                # invisible to this contract, so it is counted, not named.
                if entry.strip():
                    names.add(entry)
                else:
                    unreadable += 1
            elif isinstance(entry, dict) and len(entry) == 1:
                ((name, opts),) = entry.items()
                # The same tag with options loses its name entirely and arrives
                # as `{'option': True}` -- a scalar value is the tell, because a
                # real entry maps a name to options or to None. Reading the
                # option key as an extension name invented one called `option`.
                if (
                    isinstance(name, str)
                    and name.strip()
                    and (opts is None or isinstance(opts, dict))
                ):
                    names.add(name)
                    if isinstance(opts, dict):
                        options[name] = opts
                else:
                    unreadable += 1
            else:
                unreadable += 1
        return cls(frozenset(names), options, unreadable)

    def unknown(self) -> frozenset[str]:
        """Enabled extensions this module has never been taught about.

        Reported, not guessed: the core cannot tell a harmless unknown from one
        that introduces a container. Both corpora carry some -- the foreign one
        enables `zensical.extensions.glightbox` and `.preview`, and both were
        checked: each is a `Treeprocessor`, neither adds a block construct.
        """
        return frozenset(n for n in self.names if n not in BLOCK_CONSTRUCTS)


def container_pattern(enabled: EnabledExtensions | None = None) -> RegexPattern:
    """The container-opening pattern for a project, compiled once.

    Passed to :class:`~zenzic.core.ast.BlockTracker` at construction and never
    consulted again: the tracker must not call back per line, which would be the
    coupling-without-union that keeping one tracker avoided.
    """
    names = DEFAULT_EXTENSIONS if enabled is None else enabled.names
    parts: list[str] = list(CORE_BLOCK_CONSTRUCTS)
    for name in sorted(names):
        parts.extend(BLOCK_CONSTRUCTS.get(name, ()))
    return re.compile("|".join(parts))
