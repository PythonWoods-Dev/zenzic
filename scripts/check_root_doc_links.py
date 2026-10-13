#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Resolve the external links in each repository's root-level documentation.

WHY THIS EXISTS, AND WHY IT IS NOT PART OF ANOTHER CHECK
--------------------------------------------------------
`README.md` and `CONTRIBUTING.md` are first-party documentation that no gate
reads. Measured 2026-09-21, in both directions: a deliberately broken external
link placed in `docs/_probe_external.md` fails `zenzic check all` (91/100, gate
failed); the identical link in `README.md` passes it (100/100). The engine can
be *targeted* at a root file -- `zenzic check all README.md` reports
`./README.md - 1 file` -- and its external pass still does not reach it.

Two existing instruments were considered and declined, with the reason:

* `scripts/check_built_site_links.py` claims "every internal link in the BUILT
  site". That claim is accurate. A README is neither built-site nor internal, so
  covering it there would mean redefining the check's subject on two axes rather
  than extending it. A docstring that says what it covers, and covers it, is
  worth more than one stretched to cover everything.
* `content_roots = ["."]` in `.zenzic.toml` would bring the root into the
  engine's own scope. Measured: **21 security breaches across 10 files and 4
  security incidents**, because the repository root holds test sandboxes with
  planted secrets and the private control plane. That is why `docs_dir = "."` is
  commented out in this repository and active in `zenzic-action`, whose root
  holds neither.

WHAT THIS CAN VERIFY
--------------------
1. Every `http(s)` link in an enumerated root document resolves. A redirect is a
   pass and is reported as one: this project maintains `docs/_redirects`, so a
   301 to a page it controls is the mechanism working, not a defect.
2. All four repositories, not the one this file lives in. A gate that covers the
   core alone reports "clean" in exactly the same words as one that covers
   everything.

WHAT IT CANNOT
--------------
1. **Relative links.** A README's relative links resolve against the forge's
   rendering of the repository, not against the built site, and this check does
   not model that. It reports how many it skipped so the number is visible.
2. **Whether the destination says what the link promises.** A 200 is a page that
   exists.
3. **A third-party outage, or a host that refuses robots, from a broken page.**
   Only `404` and `410` fail this check. Every other 4xx/5xx is reported as
   *declined* and does not fail: measured, `opensource.org` answers `403` to
   every programmatic client including one sending a browser User-Agent, and a
   gate that stays red on something no edit can change is a gate people learn to
   skip. This is also why it is not in the merge gate: measured on run 34860816951, nine github.com links timed out from
   a runner and left `#233` unmergeable. External checking is scheduled work
   here, triaged rather than blocking, and this runs beside
   `zenzic check links --strict` in `external-link-sweep.yml`.

Run with `--self-test` to check the instrument in both directions.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


#: The root documents this covers, per repository. Enumerated rather than
#: globbed: a glob would silently start covering whatever lands at a root, and
#: the point of this file is that its scope is legible.
ROOT_DOCS = ("README.md", "CONTRIBUTING.md")

#: The four repositories, by directory name beside this one's parent.
REPOSITORIES = ("zenzic", "zenzic-vscode", "zenzic-action", "zenzic-mcp")

_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
_TIMEOUT = 15

#: The site this project serves, and whose redirect table it owns.
_OWN_SITE = "zenzic.dev"


def _own_redirect_sources(root: Path) -> frozenset[str]:
    """Source paths declared in this project's own `docs/_redirects`.

    A redirect is not a defect, and a redirect this project can rewrite is not
    the same risk as one somebody else can withdraw. The distinction is
    available from evidence rather than from ownership of the host: a
    `zenzic.dev` URL that moved *and* has an explicit entry in this file moved
    because this repository said so.

    Returns an empty set when the file is absent -- every redirect is then
    reported as externally controlled, which is the safe direction: it
    over-reports rather than declaring something controlled that is not.
    """
    path = root / "zenzic" / "docs" / "_redirects"
    if not path.is_file():
        return frozenset()
    sources: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        sources.add(stripped.split()[0])
    return frozenset(sources)


def _urls_in(text: str) -> list[tuple[int, str]]:
    """Every `http(s)` markdown-link target, with its 1-based line number."""
    out: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        out.extend((lineno, m.group(1)) for m in _LINK_RE.finditer(line))
    return out


def _open(url: str, *, method: str = "GET"):  # noqa: ANN202
    """Open *url*, refusing any scheme but `http`/`https`.

    The extraction regex already matches only those two, so this guard can never
    fire from this file's own call sites. It is here because a checker that
    fetches whatever it is handed is one `--root` away from reading `file:` URLs
    off disk, and the guard costs two lines.
    """
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"refusing non-HTTP scheme: {url!r}")
    request = urllib.request.Request(  # noqa: S310 -- scheme checked above
        url, method=method, headers={"User-Agent": "zenzic-link-check"}
    )
    return urllib.request.urlopen(request, timeout=_TIMEOUT)  # noqa: S310


def _status(url: str) -> tuple[int | None, str]:
    """`(status, note)`; `None` when the request could not be made at all."""
    try:
        with _open(url, method="HEAD") as response:
            # `urlopen` follows redirects, so a 301 arrives here as 200 and the
            # only evidence it happened is that the final URL moved. Counting
            # `300 <= status < 400` could never fire -- a field that cannot vary
            # is not data.
            final = response.geturl()
            return response.status, "" if final == url else f" (redirected -> {final})"
    except urllib.error.HTTPError as exc:
        # Some hosts refuse HEAD and serve GET, and they do not agree on which
        # status to refuse with. Measured 2026-09-21: the VS Code Marketplace
        # answers HEAD on a *published* extension with **404** -- this check
        # reported its install link broken, and the page returns 200 to GET.
        # The retry covered 403 and 405 only, which is how a false positive
        # reached a report. Any 4xx is retried now: a genuine 404 answers 404
        # to GET as well, so the retry costs one request and cannot hide a
        # real break.
        if 400 <= exc.code < 500:
            try:
                with _open(url) as response:
                    return response.status, " (HEAD refused, GET accepted)"
            except Exception as retry_exc:  # noqa: BLE001
                return exc.code, f" (GET retry: {type(retry_exc).__name__})"
        return exc.code, ""
    except Exception as exc:  # noqa: BLE001
        return None, f" ({type(exc).__name__})"


def _self_test() -> int:
    """Both directions, against the instrument's own subject."""
    cases = [
        ("a page that exists", "https://zenzic.dev/how-to/configure-adapter/", True),
        ("a page that does not", "https://zenzic.dev/definitely-not-a-page-xyz123/", False),
        # A host that answers HEAD with 404 on a page it serves. This case is
        # here because the instrument got it wrong once, and a self-test that
        # only exercises well-behaved hosts would have stayed green through it.
        (
            "a published extension whose host refuses HEAD",
            "https://marketplace.visualstudio.com/items?itemName=pythonwoods.zenzic-vscode",
            True,
        ),
    ]
    failures = 0
    for label, url, should_pass in cases:
        status, note = _status(url)
        ok = status is not None and 200 <= status < 400
        if ok is not should_pass:
            print(
                f"SELF-TEST FAILED: {label} -> {status}{note}, expected {'pass' if should_pass else 'fail'}"
            )
            failures += 1

    extracted = _urls_in("see [a](https://example.com/x) and `[b](https://example.com/y)`\n")
    if len(extracted) != 2:
        print(f"SELF-TEST FAILED: extraction found {len(extracted)} links, expected 2")
        failures += 1

    if failures:
        return 1
    print(f"self-test passed: {len(cases)} case(s), both directions, plus extraction")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="check the instrument, then exit")
    parser.add_argument("--root", default=None, help="directory holding the four repositories")
    args = parser.parse_args()

    if args.self_test:
        return _self_test()

    here = Path(__file__).resolve().parent.parent
    root = Path(args.root).resolve() if args.root else here.parent

    broken: list[str] = []
    refused: list[str] = []
    external_redirects: list[str] = []
    checked = skipped_relative = own_redirects = 0
    scanned: list[str] = []
    own_sources = _own_redirect_sources(root)

    for repo in REPOSITORIES:
        for name in ROOT_DOCS:
            path = root / repo / name
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            scanned.append(f"{repo}/{name}")
            skipped_relative += len(re.findall(r"\[[^\]]*\]\((?!https?://|#)[^)\s]+\)", text))
            for lineno, url in _urls_in(text):
                checked += 1
                status, note = _status(url)
                if "(redirected" in note:
                    parsed = urllib.parse.urlparse(url)
                    if parsed.netloc == _OWN_SITE and parsed.path in own_sources:
                        own_redirects += 1
                    else:
                        external_redirects.append(f"{repo}/{name}:{lineno}: {url}{note}")
                if status is None:
                    refused.append(f"{repo}/{name}:{lineno}: {url} -- unreachable{note}")
                elif status in (404, 410):
                    # The page is not there. Everything else in the 4xx/5xx
                    # range is the host declining to answer *us*, which no edit
                    # to this repository can fix. Measured 2026-09-21:
                    # `opensource.org/licenses/Apache-2.0` answers 403 to every
                    # programmatic client, browser User-Agent included. Failing
                    # on it forever would teach a reader to ignore this gate,
                    # which is the failure mode the codebase argues against
                    # wherever a red that cannot be actioned appears.
                    broken.append(f"{repo}/{name}:{lineno}: {url} -- HTTP {status}{note}")
                elif status >= 400:
                    refused.append(f"{repo}/{name}:{lineno}: {url} -- HTTP {status}{note}")

    if not scanned:
        print(f"FAILED: no root documents found under {root} -- nothing was checked")
        return 1

    # The redirect classification is printed whether or not something is broken.
    # It was behind the early return, so a single unresolvable link hid the
    # dependency picture for every other link in the sweep -- a report that
    # tells you less the more there is wrong with it.
    def _report_soft() -> None:
        if refused:
            print(f"  {len(refused)} link(s) the host declined to answer (not a missing page):")
            for line in refused:
                print(f"    {line}")

    def _report_redirects() -> None:
        print(
            f"  {own_redirects} reach their page through a redirect this project declares in "
            f"docs/_redirects ({len(own_sources)} entries) -- rewritable here if one breaks"
        )
        if external_redirects:
            # Reported, not failed. A redirect that works is not a break; it is
            # a dependency on somebody else continuing to serve it, which is the
            # standing risk this repository already tracks for its renamed
            # GitHub namespace. Naming them is what lets that row be measured
            # instead of argued.
            print(
                f"  {len(external_redirects)} depend on a redirect this project does not control:"
            )
            for line in external_redirects:
                print(f"    {line}")

    if broken:
        print(f"FAILED: {len(broken)} unresolvable link(s) in root documentation:")
        for line in broken:
            print(f"  {line}")
        _report_soft()
        _report_redirects()
        return 1

    print(
        f"root doc links: {checked} external link(s) across {len(scanned)} document(s) "
        f"in {len(REPOSITORIES)} repositories, all resolve; "
        f"{skipped_relative} relative link(s) not checked"
    )
    _report_soft()
    _report_redirects()
    return 0


if __name__ == "__main__":
    sys.exit(main())
