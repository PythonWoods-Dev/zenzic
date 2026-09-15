#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Enforces the staggered-publication link schedule for docs/blog/posts/.

The Foundations series and the two launch posts publish on a staggered
schedule, one post per day. The agreed scheme: a post never links forward to
a successor that isn't live yet; that link is added back in, manually and
reviewed, on the day the successor actually goes live. Nothing before this
script enforced that -- a real `mkdocs build --strict` builds clean even when
every post in the series links forward to a still-draft target, because the
blog plugin silently excludes draft posts from the build rather than treating
a link into one as broken.

Two modes:

    python3 scripts/check_blog_link_schedule.py
        Hard gate (wired into pre-commit + CI): fails if any non-draft
        (live) post under docs/blog/posts/ links to a post that is still
        `draft: true`. A link to another live post, in either direction,
        is always fine -- only a live-to-draft edge is a violation.

    python3 scripts/check_blog_link_schedule.py --schedule
        Reporting mode (run manually as `just blog-link-schedule` before
        each day's publish action): reads scripts/blog_link_schedule.json,
        the exact paragraphs pulled out of the 9 posts during the
        V031_STAGGERED_LINK_AUDIT_AND_AUTOMATION_PROPOSAL audit, and states
        for each whether its target has gone live (safe to paste back in
        now) or is still draft (not yet). Always exits 0 -- it is a report,
        not a gate.

Both modes accept --posts-dir to point at a different directory, which is
how this script's own test fixtures exercise it without touching the real
posts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POSTS_DIR = REPO_ROOT / "docs" / "blog" / "posts"
DEFAULT_SCHEDULE_FILE = REPO_ROOT / "scripts" / "blog_link_schedule.json"

FRONTMATTER_RE = re.compile(r"\A---\n(.*?\n)---\n", re.DOTALL)
INTERNAL_LINK_RE = re.compile(r"\]\((\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md)(?:#[^)]+)?\)")


def _load_frontmatter(text: str) -> dict[str, Any]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    import yaml

    return yaml.safe_load(match.group(1)) or {}


def _is_draft(meta: dict[str, Any]) -> bool:
    return bool(meta.get("draft", False))


def _scan_posts(posts_dir: Path) -> dict[str, dict[str, Any]]:
    """Map filename -> {"draft": bool, "links": set[filename]}."""
    posts: dict[str, dict[str, Any]] = {}
    for path in sorted(posts_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta = _load_frontmatter(text)
        links = set(INTERNAL_LINK_RE.findall(text))
        posts[path.name] = {"draft": _is_draft(meta), "links": links}
    return posts


def check(posts_dir: Path) -> int:
    posts = _scan_posts(posts_dir)
    if not posts:
        print(f"error: no posts found under {posts_dir}", file=sys.stderr)
        return 1

    violations: list[str] = []
    for name, info in posts.items():
        if info["draft"]:
            continue  # a draft post linking anywhere is not yet a live claim
        for target in info["links"]:
            target_info = posts.get(target)
            if target_info is None:
                continue  # not one of the staggered posts (already-published, external)
            if target_info["draft"]:
                violations.append(
                    f"{name} is live and links to {target}, which is still draft: true "
                    "-- a reader could click through to an unpublished page"
                )

    if violations:
        print(f"blog link schedule: {len(violations)} violation(s)", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    live = sum(1 for info in posts.values() if not info["draft"])
    print(f"blog link schedule OK -- {live}/{len(posts)} posts live, no live-to-draft links")
    return 0


def schedule(posts_dir: Path, schedule_file: Path) -> int:
    if not schedule_file.is_file():
        print(f"error: {schedule_file} not found", file=sys.stderr)
        return 1

    posts = _scan_posts(posts_dir)
    entries = json.loads(schedule_file.read_text(encoding="utf-8"))

    if not entries:
        print("blog link schedule: no pending links recorded")
        return 0

    for entry in entries:
        target_info = posts.get(entry["target"])
        if target_info is None:
            status = "UNKNOWN (target not found under posts dir)"
        elif target_info["draft"]:
            status = "PENDING (target still draft)"
        else:
            status = "READY (target is live -- safe to paste the link back in)"
        print(f"[{status}] {entry['source']} -> {entry['target']}")
        print(f"    text: {entry['paragraph'].splitlines()[0][:100]}...")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--posts-dir",
        type=Path,
        default=DEFAULT_POSTS_DIR,
        help="directory containing blog posts (default: docs/blog/posts)",
    )
    parser.add_argument(
        "--schedule-file",
        type=Path,
        default=DEFAULT_SCHEDULE_FILE,
        help="path to the pending-links JSON file (default: scripts/blog_link_schedule.json)",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="report mode: show which pending links are ready to re-add",
    )
    args = parser.parse_args()

    if args.schedule:
        return schedule(args.posts_dir, args.schedule_file)
    return check(args.posts_dir)


if __name__ == "__main__":
    sys.exit(main())
