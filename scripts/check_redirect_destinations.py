#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Every ledger destination must resolve to a page in the built site.

`docs/_redirects` is written by hand and its destinations are never checked
against the build.  A page can therefore be deleted or renamed while rules keep
pointing at its old address: the rules still work against the *deployed* site,
which was built before the deletion, and start returning 404 the moment the new
build ships.  That is a regression a release introduces rather than one it
inherits, and nothing in `just verify` could see it.

Six such rules were found on 2026-09-13, five from a documentation pruning that
retargeted the ``/docs/`` spellings and not the bare ones, and one from removing
``Z504``.  All six returned 200 from the live deploy and 404 from the next.

Resolution follows the ledger transitively -- a destination may itself be a
redirect source -- and stops at the first target that exists in the build.
Fragments and query strings are stripped: they are resolved by the client.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER = REPO_ROOT / "docs" / "_redirects"
DEFAULT_SITE = REPO_ROOT / "site"
MAX_HOPS = 10


def load_rules(ledger: Path) -> dict[str, str]:
    rules: dict[str, str] = {}
    for raw in ledger.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            rules[parts[0]] = parts[1]
    return rules


def page_exists(site: Path, url_path: str) -> bool:
    """True when *url_path* is served by the built site."""
    p = url_path.split("#")[0].split("?")[0].strip("/")
    if not p:
        return (site / "index.html").is_file()
    return (
        (site / p).is_file()
        or (site / p / "index.html").is_file()
        or (site / f"{p}.html").is_file()
    )


def resolve(rules: dict[str, str], dest: str, site: Path) -> tuple[bool, list[str]]:
    """Follow the ledger from *dest* until a real page, a loop, or exhaustion.

    A server stops at the first destination that is a real page, so the walk stops
    there too. Without that, a rule whose destination is a live page still matches
    the slash-normalising rule for the same path and looks like a second hop --
    which produced six phantom chains on the first measurement of this ledger.
    """
    chain = [dest]
    cur = dest
    for _ in range(MAX_HOPS):
        if page_exists(site, cur):
            return True, chain
        bare = cur.split("#")[0].split("?")[0]
        nxt = rules.get(bare) or rules.get(bare.rstrip("/")) or rules.get(bare.rstrip("/") + "/")
        if not nxt or nxt in chain:
            break
        chain.append(nxt)
        cur = nxt
    return page_exists(site, cur), chain


def main(argv: list[str]) -> int:
    site = Path(argv[1]) if len(argv) > 1 else DEFAULT_SITE
    if not site.is_dir():
        print(
            f"redirect-destination gate: no built site at {site} — run `mkdocs build` first",
            file=sys.stderr,
        )
        return 2
    rules = load_rules(LEDGER)
    broken: list[tuple[str, list[str]]] = []
    chained: list[tuple[str, list[str]]] = []
    for src, dest in sorted(rules.items()):
        ok, chain = resolve(rules, dest, site)
        if not ok:
            broken.append((src, chain))
        elif len(chain) > 1:
            # Two correct rules written at different times compose into a chain:
            # a /docs/ prefix rule and, later, a rule for a page that was removed.
            # Each is right; together they cost a reader an extra round trip, and
            # a crawler treats a chain as signal dilution. Point the first rule at
            # the final destination instead.
            chained.append((src, chain))

    if chained and not broken:
        print(
            f"redirect-destination gate: FAILED — {len(chained)} rule(s) reach their "
            f"page through another redirect"
        )
        for src, chain in chained[:20]:
            print(f"  {src}\n      → {' → '.join(chain)}  ({len(chain)} hops)")
        return 1

    if broken:
        print(f"redirect-destination gate: FAILED — {len(broken)} rule(s) point at nothing")
        for src, chain in broken[:40]:
            print(f"  {src}\n      → {' → '.join(chain)}  (no such page in the build)")
        if len(broken) > 40:
            print(f"  … and {len(broken) - 40} more")
        return 1

    print(
        f"redirect-destination gate: clean — {len(rules)} rule(s), "
        f"every destination resolves in one hop in {site.name}/"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
