# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Scan a pinned external corpus and compare the findings **per code**.

WHY THIS EXISTS
---------------
A high score on our own repository measures agreement between an engine and the
corpus it grew up with. It does not measure correctness. This is the project's
only independent measurement, and until now it existed as a document rather than
as a control.

WHY PER CODE AND NOT A TOTAL
----------------------------
A total that stays the same while two codes move in opposite directions passes
and means nothing. The comparison below is per code, and a code appearing or
disappearing is as much a difference as a count changing.

THE COUPLING THAT IS THE POINT
------------------------------
An unexplained change is a regression. An explained one -- a false positive
fixed, a code made opt-in -- updates the pinned figure with ``--update``, **in
the same commit as the change that caused it**, with the reason in the commit
message. The numbers move only when someone says why.

THE BLIND SPOT, STATED HERE RATHER THAN DISCOVERED
--------------------------------------------------
A corpus pinned at a commit exercises the constructs that corpus contains, and
nothing else. This cycle closed **four** defects whose corpora moved not at all:
nested fences, backslash escapes, setext headings, and a frontmatter closed with
YAML's document-end marker. Each was real, each was invisible to both corpora,
and each was covered by a probe and a suite instead.

**One pinned corpus is better than none and is not coverage.** It catches a
regression on somebody else's documentation; it says nothing about a construct
neither corpus writes.

This runs outside the pre-push path on purpose: it clones a repository, and
network dependence in a pre-push hook cost this project five failed pushes with
no diagnosable output.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path


PIN_FILE = Path(__file__).resolve().parent / "external-corpus-pin.json"


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    # The argument list is built from this repository's own pinned JSON and from
    # literals, never from user input, and the precedent is the other scripts here.
    return subprocess.run(  # noqa: S603
        cmd, cwd=cwd, capture_output=True, text=True, check=False
    )


def _fetch(repo: str, commit: str, into: Path) -> None:
    """Shallow-fetch exactly the pinned commit.

    `clone --depth 1` gets whatever the default branch points at today, which is
    not a pin. Init plus a fetch of the commit itself is, and it fails loudly
    when the commit is gone -- which is the condition that made the previous
    pin worthless: it named a commit that is not a ref in the repository the
    batch file named.
    """
    _run(["git", "init", "-q", str(into)])
    _run(["git", "remote", "add", "origin", repo], cwd=into)
    got = _run(["git", "fetch", "-q", "--depth", "1", "origin", commit], cwd=into)
    if got.returncode != 0:
        raise SystemExit(
            f"FAILED: commit {commit} is not fetchable from {repo}.\n"
            f"  {got.stderr.strip()}\n"
            "  A pin that names a commit the repository does not have is not a pin."
        )
    _run(["git", "checkout", "-q", "FETCH_HEAD"], cwd=into)


def _count_sources(root: Path) -> int:
    """Markdown sources in the fetched tree.

    The third leg of the pin. Batch 10 recorded a premise wrong in three ways --
    repository, commit and file count -- and a pin that names only the first two
    still cannot tell a corpus that shrank from an engine that stopped looking.
    A commit fixes the tree, so this number is a constant; when it moves, either
    the fetch is not what it claims or this script is walking somewhere else.
    """
    return sum(1 for p in root.rglob("*") if p.suffix in {".md", ".mdx"} and ".git" not in p.parts)


def _scan(root: Path) -> Counter[str]:
    """Findings per code, from the JSON payload rather than the rendered text.

    The text surface renders a security breach separately, so it under-counts by
    one on this corpus. The payload carries every finding under one key.
    """
    out = _run(
        ["uv", "run", "zenzic", "check", "all", "--no-external", "--format", "json"],
        cwd=root,
    )
    start = out.stdout.find("{")
    if start < 0:
        raise SystemExit(f"FAILED: no JSON payload from the engine.\n{out.stderr[-2000:]}")
    payload = json.loads(out.stdout[start:])
    return Counter(f.get("code") for f in payload.get("findings", []))


def _prepare(root: Path, setup: dict[str, str] | None) -> None:
    """Write the configuration a corpus needs before it can be scanned.

    The first corpus needs none: `zensical/docs` carries its own `mkdocs.yml`
    and Zenzic discovers it. A generator Zenzic has no adapter for needs the
    `prebuilt` recipe written for it, and writing it here is what makes the
    baseline reproducible rather than a number someone once took by hand.

    The manifest is derived positionally from the source tree, which is what
    Astro's content collections permit. The locale prefix is not optional and
    is not cosmetic: without it the manifest is complete, well-formed, and
    resolves nothing.
    """
    if not setup:
        return
    docs_rel = setup["docs_dir"]
    docs = root / docs_rel
    prefix = setup.get("url_prefix", "/")
    routes: dict[str, dict[str, str]] = {}
    for path in sorted(docs.rglob("*")):
        if path.suffix not in {".md", ".mdx"}:
            continue
        rel = path.relative_to(docs).as_posix()
        slug = rel[: -len(path.suffix)].removesuffix("/index")
        routes[rel] = {"url": f"{prefix}{slug}/" if slug else prefix, "status": "REACHABLE"}
    (root / ".zenzic-vsm.json").write_text(json.dumps(routes, indent=1), encoding="utf-8")
    (root / ".zenzic.toml").write_text(
        f'docs_dir = "{docs_rel}"\nabsolute_path_allowlist = ["/"]\n\n'
        '[build_context]\nengine = "prebuilt"\n',
        encoding="utf-8",
    )


def _count_sources_in(root: Path, docs_rel: str | None) -> int:
    """Markdown sources, optionally restricted to the corpus's own docs tree."""
    base = root / docs_rel if docs_rel else root
    if not base.is_dir():
        return 0
    return sum(1 for p in base.rglob("*") if p.suffix in {".md", ".mdx"} and ".git" not in p.parts)


def _one(pin: dict[str, object], *, update: bool) -> tuple[int, str]:
    """Fetch, prepare and scan one corpus. Returns (exit code, one-line report)."""
    raw_setup = pin.get("setup")
    setup: dict[str, str] | None = raw_setup if isinstance(raw_setup, dict) else None
    docs_rel = setup["docs_dir"] if setup else None
    name = f"{pin['repository']} at {str(pin['commit'])[:8]}"
    raw_counts = pin["counts"]
    expected: dict[str, int] = dict(raw_counts) if isinstance(raw_counts, dict) else {}

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "corpus"
        _fetch(str(pin["repository"]), str(pin["commit"]), root)
        _prepare(root, setup)
        files = _count_sources_in(root, docs_rel)
        actual = _scan(root)

    if not update and files != pin["file_count"]:
        return 1, (
            f"FAILED: the pinned tree does not have the pinned number of sources.\n"
            f"  {name}\n"
            f"  pinned {pin['file_count']} markdown sources, measured {files}\n\n"
            "  A commit fixes the tree, so this number cannot move on its own. Either the\n"
            "  fetch is not the commit it claims, or this script no longer walks the corpus."
        )

    if update:
        pin["counts"] = dict(sorted(actual.items()))
        pin["file_count"] = files
        return 0, f"{name}: {sum(actual.values())} findings across {len(actual)} codes"

    problems = []
    for code in sorted(set(expected) | set(actual)):
        want, have = expected.get(code, 0), actual.get(code, 0)
        if want != have:
            verb = "appeared" if want == 0 else "disappeared" if have == 0 else "changed"
            problems.append(f"  {code}: pinned {want}, measured {have} -- {verb}")
    if problems:
        return 1, (
            f"FAILED: the external corpus reports different findings.\n  {name}\n"
            + "\n".join(problems)
            + "\n\n  An unexplained change is a regression. An explained one updates this pin\n"
            "  with --update, in the same commit as the change that caused it."
        )
    return 0, (
        f"{name}: {sum(actual.values())} findings across {len(actual)} codes "
        f"over {files} sources, unchanged"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update",
        action="store_true",
        help="rewrite the pinned counts; use only in the commit that caused the change",
    )
    args = parser.parse_args(argv)

    data = json.loads(PIN_FILE.read_text(encoding="utf-8"))
    # One corpus was one object; two are a list under "corpora". The older shape
    # is still read so the file can be rolled back without editing this script.
    corpora: list[dict[str, object]] = data["corpora"] if "corpora" in data else [data]

    failed = 0
    for pin in corpora:
        code, line = _one(pin, update=args.update)
        failed |= code
        print(line)

    if args.update:
        PIN_FILE.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("pins updated")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
