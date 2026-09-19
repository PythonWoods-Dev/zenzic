#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Skip a tree-deterministic verification stage whose verdict this tree already earned.

`just verify` runs before a commit and again inside the pre-push hook, so a
compliant push pays the whole gate twice on a byte-identical tree. Measured on
2026-09-17: pytest with coverage 260 s, the local gates 110 s, the docs build
29 s -- about 400 of 445 seconds -- for stages whose verdict depends on nothing
but the tree. The three stages that reach outside the tree (`pip-audit`, the
structural audit and the score, which probe external links) are never cached.

    verdict_cache.py run <label> -- <command...>
    verdict_cache.py key

`run` executes the command unless a green verdict for `<label>` is recorded for
the current tree key, and records one when the command exits 0. Nothing about
the checks changes: the same commands run, with the same arguments, just not a
second time on a tree that has not changed.

The key is the content of everything a stage can read:

* `git write-tree` over a temporary index built with `add -A`, so untracked
  files count by content (a plain `write-tree` ignores them entirely, which a
  brand-new unstaged test file would slip through), and a deletion or a rename
  changes the tree like any other content change;
* the gitignored local trees and recipe file the local gates read (`PRIVATE`
  below), hashed by content when present.

Deliberately *not* in the key: `git status` output. The row that designed this
cache proposed composing it in, but staging and committing change the status
lines without changing a byte the stages read -- and the whole point is that
`just verify`, then `git commit`, then the pre-push hook meets the same tree.

Disabled under `CI` (a runner never sees the same tree twice) and with
`ZENZIC_VERDICT_CACHE=0`. Verdicts live in `.zenzic_cache/verdicts/`, already
gitignored and already a system-excluded directory.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess  # noqa: S404 - build tooling, not the Zero Subprocess Core
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO_ROOT / ".zenzic_cache" / "verdicts"
PRIVATE = (".claude", ".human", ".justfile.local")
SKIP_DIRS = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})


def _git(root: Path, *argv: str, env: dict[str, str] | None = None) -> str:
    done = subprocess.run(  # noqa: S603
        ["git", *argv],  # noqa: S607
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        env=env,  # noqa: S607
    )
    return done.stdout.strip()


def _private_digest(root: Path) -> str:
    h = hashlib.sha256()
    for name in PRIVATE:
        p = root / name
        if p.is_file():
            h.update(name.encode())
            h.update(p.read_bytes())
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if (
                    not f.is_file()
                    or SKIP_DIRS.intersection(f.parts)
                    or f.suffix in (".pyc", ".pyo")
                ):
                    continue
                h.update(str(f.relative_to(root)).encode())
                h.update(f.read_bytes())
    return h.hexdigest()


def tree_key(root: Path = REPO_ROOT) -> str:
    """One hash for everything a tree-deterministic stage can read."""
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / "index"))
        _git(root, "read-tree", "HEAD", env=env)
        _git(root, "add", "-A", env=env)
        tree = _git(root, "write-tree", env=env)
    h = hashlib.sha256()
    h.update(tree.encode())
    h.update(_private_digest(root).encode())
    return h.hexdigest()


def enabled() -> bool:
    return not os.environ.get("CI") and os.environ.get("ZENZIC_VERDICT_CACHE", "1") != "0"


def run(label: str, command: list[str], root: Path = REPO_ROOT, cache_dir: Path = CACHE_DIR) -> int:
    if not command:
        print("verdict cache: no command given", file=sys.stderr)
        return 3
    if not enabled():
        return subprocess.run(command, cwd=root, check=False).returncode  # noqa: S603
    key = tree_key(root)
    marker = cache_dir / label / key
    if marker.is_file():
        stamp = marker.read_text(encoding="utf-8").splitlines()[0] if marker.stat().st_size else ""
        print(
            f"verdict cache: `{label}` already green for this exact tree ({key[:12]}, {stamp}); "
            "not re-run. ZENZIC_VERDICT_CACHE=0 forces it."
        )
        return 0
    code = subprocess.run(command, cwd=root, check=False).returncode  # noqa: S603
    if code == 0:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}\n{' '.join(command)}\n",
            encoding="utf-8",
        )
        print(f"verdict cache: `{label}` recorded green for tree {key[:12]}")
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Skip a tree-deterministic stage already green for this tree."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("label")
    r.add_argument("command", nargs=argparse.REMAINDER)
    sub.add_parser("key")
    args = parser.parse_args(argv)
    if args.cmd == "key":
        print(tree_key())
        return 0
    command = [c for c in args.command if c != "--"]
    return run(args.label, command)


if __name__ == "__main__":
    raise SystemExit(main())
