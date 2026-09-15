#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Run the project's own credential scanner over the whole tree in CI.

    python3 scripts/ci_secret_scan.py [--self-test]

**What this replaces.** `secret-scan.yml` was 22 lines, one step, and two `echo`
statements deferring to a platform feature that was disabled in every repository in
this ecosystem. It reported `success` on every commit and had never scanned
anything — a green check named `Scan`, in a credential scanner's own repository.

**Why the exclusion set is the hard part, and how it avoids becoming a bypass.**
The tree deliberately contains pattern-valid, non-functional example secrets: the
`Z201` fixture, a red-team sandbox, a security lab. A directory-level exclusion for
those would be the shape this project closed once already at the hook level, where a
`--staged` flag narrowed a scan to an always-empty set and the hook passed forever.

So nothing is excluded from the *scan*. It runs over everything, and this script
fails unless every finding matches an entry in `ALLOWED` by **path and secret type
together**. A new credential in a brand-new file fails. A new credential in a
fixture file fails. A *different kind* of credential in the same fixture file fails.
The allowlist forgives exactly the findings that were examined and named, and
nothing adjacent to them.

Exit 0 when every finding is an allowlisted fixture, 1 otherwise.

What this does NOT check, stated here rather than discovered later
-----------------------------------------------------------------
1. **It scans what is checked out.** A credential in history but not at HEAD is
   invisible to it; that is GitHub's platform secret scanning's job, which is now
   enabled on all four repositories and scans history.
2. **It trusts the scanner's own signature set.** A credential shape `zenzic guard`
   does not recognise is not found here either. The two layers are deliberately
   different: this one is the project's own patterns, the platform's is its
   provider list, and neither subsumes the other.
3. **The allowlist is a list, and a list goes stale.** A fixture that is deleted
   leaves a stale entry behind, which weakens nothing but records something untrue.
   The self-test therefore asserts every allowlisted path still exists.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

#: (path, secret type) pairs that are deliberate fixtures. Keyed on both halves so a
#: new *kind* of secret in a known fixture file is still a failure. Each carries the
#: reason it exists, because an allowlist entry without one becomes unreviewable.
ALLOWED: dict[tuple[str, str], str] = {
    ("examples/z201-credentials/docs/setup.md", "aws-access-key"): (
        "the Z201 lab scenario — its whole purpose is to hold a credential the scanner finds"
    ),
    ("tests/sandboxes/hero_specimen/docs/secrets.md", "aws-access-key"): (
        "the hero screenshot specimen; the finding is the subject of the image"
    ),
}

#: Deliberately NOT here, and the reason is a blind spot worth naming. GitHub's own
#: secret scanning reported four alerts in `examples/security_lab/` — a directory that
#: does not exist at HEAD. Those are historical: the platform scans history, this
#: script scans the checkout. Adding them would allowlist paths that are absent, which
#: the self-test rejects on purpose. History is the platform's job, and it is enabled
#: on all four repositories as of 2026-09-12.


def scan(root: Path) -> list[dict[str, str]]:
    """Every finding `zenzic guard scan` reports for *root*, as repo-relative dicts."""
    # `zenzic` from PATH where the project provides it; `uvx` otherwise, so the same
    # script runs in a repository that has no Python project of its own. One shape
    # across four repositories rather than four implementations of one rule.
    if shutil.which("zenzic"):
        argv = ["zenzic"]
    else:
        argv = ["uvx", "--from", "zenzic", "zenzic"]
    proc = subprocess.run(  # noqa: S603
        [*argv, "guard", "scan", str(root), "--format", "json", "--no-header"],  # noqa: S607
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(f"FATAL: the scanner produced no JSON.\n{proc.stdout[-800:]}", file=sys.stderr)
        raise SystemExit(2) from None
    out: list[dict[str, str]] = []
    for f in payload.get("findings", []):
        try:
            rel = Path(str(f["file"])).resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel = str(f["file"])
        out.append({"path": rel, "type": str(f.get("type", "")), "line": str(f.get("line", ""))})
    return out


def tracked_paths(root: Path) -> set[str]:
    """Every git-tracked path, which is exactly what a CI checkout contains.

    Scoping to tracked files is what makes a local run and a CI run agree. The
    private control plane lives in gitignored directories and holds credential
    examples of its own — advisory drafts, an archived priority row quoting a
    finding — so an unscoped local run reports nine findings that CI can never see.
    A check whose verdict depends on which machine ran it is not a check.
    """
    proc = subprocess.run(  # noqa: S603
        ["git", "ls-files"],  # noqa: S607
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {line for line in proc.stdout.splitlines() if line}


def unexpected(
    findings: list[dict[str, str]], tracked: set[str] | None = None
) -> list[dict[str, str]]:
    """Findings the allowlist does not forgive — matched on path AND type.

    Untracked findings are dropped rather than forgiven: they are not in the artifact
    under review. `tracked=None` skips the filter, which is what the self-test uses so
    its synthetic paths do not have to exist.
    """
    scoped = findings if tracked is None else [f for f in findings if f["path"] in tracked]
    return [f for f in scoped if (f["path"], f["type"]) not in ALLOWED]


def _self_test() -> bool:
    """The comparison must reject a planted finding and accept a known fixture.

    Runs before any verdict on the real tree. The third case is the one that makes
    the allowlist reviewable: an entry naming a file that no longer exists is a claim
    about something absent, and it should be removed rather than left to look load-bearing.
    """
    known = next(iter(ALLOWED))
    fixture = {"path": known[0], "type": known[1], "line": "1"}
    planted = {"path": "src/zenzic/core/scanner.py", "type": "aws-access-key", "line": "1"}
    same_file_new_type = {"path": known[0], "type": "stripe-key", "line": "1"}

    if unexpected([fixture]):
        print("self-test FAILED: a known fixture was reported unexpected", file=sys.stderr)
        return False
    if not unexpected([planted]):
        print("self-test FAILED: a planted credential in source was forgiven", file=sys.stderr)
        return False
    if not unexpected([same_file_new_type]):
        print(
            "self-test FAILED: a NEW secret type in a fixture file was forgiven — "
            "the allowlist is behaving as a path-level bypass",
            file=sys.stderr,
        )
        return False
    missing = [p for (p, _t) in ALLOWED if not (REPO_ROOT / p).exists()]
    if missing:
        print(f"self-test FAILED: allowlist names absent path(s): {missing}", file=sys.stderr)
        return False
    print(f"self-test passed: 4 case(s); {len(ALLOWED)} allowlisted fixture finding(s)")
    return True


def main() -> int:
    if not _self_test():
        return 2
    if "--self-test" in sys.argv:
        return 0

    tracked = tracked_paths(REPO_ROOT)
    findings = [f for f in scan(REPO_ROOT) if f["path"] in tracked]
    bad = unexpected(findings, tracked)
    print(
        f"ci-secret-scan: {len(tracked)} tracked file(s) scanned; {len(findings)} finding(s); "
        f"{len(findings) - len(bad)} allowlisted fixture(s); {len(bad)} unexpected"
    )
    if bad:
        print(f"\nFAILED: {len(bad)} credential(s) outside the fixture allowlist:", file=sys.stderr)
        for f in bad:
            print(f"  {f['path']}:{f['line']}  {f['type']}", file=sys.stderr)
        print(
            "\nIf one of these is a deliberate fixture, add it to ALLOWED in "
            "scripts/ci_secret_scan.py with the reason it exists. If it is not, "
            "rotate it immediately — it is in the tree.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
