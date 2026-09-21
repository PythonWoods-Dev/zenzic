#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A committed build artifact matches what its declared build command produces.

`docs/assets/css/zenzic-tailwind.min.css` is 41 KB of committed CSS that no gate
compared against a rebuild. Two consequences shipped because of that, and neither
was visible to any existing check:

1. **A hand-added SPDX header.** The committed bundle carried one; the CLI does
   not emit it and a clean rebuild drops it. `reuse lint` passed throughout,
   because `REUSE.toml`'s `docs/assets/**` block covers the path — a compliance
   gate covering the file with an unrelated exclusion, which is why nothing
   noticed it was hand-edited.
2. **An input the repository does not contain.** The bundle wired 114 selectors
   to `[data-md-color-scheme=slate]`, and nothing in the repo produced that:
   `tailwind.config.js` has never had a `darkMode` key. Pinning the CLI version
   made the *version* reproducible; it did not make the *artifact* reproducible,
   and only rebuilding and diffing showed the difference.

WHAT THIS CAN VERIFY
--------------------
1. Rebuilding the CSS from `tailwind-input.css` reproduces the committed bundle.
   The build was measured deterministic before this check was written: two
   consecutive runs are byte-identical. The only permitted difference is the
   trailing newline that the `end-of-file-fixer` pre-commit hook adds after
   generation.
2. `package.json` and `package-lock.json` agree on the pinned version. A lockfile
   that no longer matches its manifest is the same class of drift, and nothing
   else checks it: CI has no Node by design, so `npm ci` never runs.

WHAT THIS CANNOT VERIFY, stated so the gate's name does not imply more
----------------------------------------------------------------------
**Anything in CI.** Both checks need Node, which CI deliberately does not have.
This runs in `_local-gates`, so it catches drift on the machine that can create
it — the one running the build — and not on the machine that cannot.

**That the build command in the README is the one a human ran.** It verifies the
command in `package.json` reproduces the artifact. If someone builds another way
and the output happens to match, this says nothing about that.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "docs" / "assets" / "css" / "zenzic-tailwind.min.css"
INPUT = ROOT / "tailwind-input.css"


def _npm_available() -> bool:
    return shutil.which("npx") is not None and (ROOT / "node_modules").is_dir()


def check_lockfile_agrees() -> list[str]:
    """`package.json`'s pin and `package-lock.json`'s resolution must be the same."""
    manifest = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    lock_path = ROOT / "package-lock.json"
    if not lock_path.is_file():
        return ["package-lock.json is missing while package.json declares dependencies"]
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    for name, pinned in manifest.get("devDependencies", {}).items():
        entry = lock.get("packages", {}).get(f"node_modules/{name}", {})
        resolved = entry.get("version")
        if resolved != pinned:
            problems.append(
                f"package.json pins {name} at {pinned}, package-lock.json resolves {resolved!r}"
                " — run `npm install --package-lock-only` and commit the result"
            )
    return problems


def check_bundle_matches_a_rebuild() -> list[str]:
    """Rebuild into a temporary file and compare, ignoring the added trailing newline."""
    if not _npm_available():
        return []
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "rebuilt.css"
        npx = shutil.which("npx")
        if npx is None:  # pragma: no cover — guarded by _npm_available above
            return []
        result = subprocess.run(  # noqa: S603 — absolute path, fixed argv, no shell
            [npx, "--no-install", "tailwindcss", "-i", str(INPUT), "-o", str(out), "--minify"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not out.is_file():
            return [f"the declared build command failed: {result.stderr.strip()[:200]}"]
        rebuilt = out.read_text(encoding="utf-8").rstrip("\n")
    committed = BUNDLE.read_text(encoding="utf-8").rstrip("\n")
    if rebuilt == committed:
        return []
    detail = f"{len(committed)} bytes committed, {len(rebuilt)} rebuilt"
    if "SPDX" in committed[:400] and "SPDX" not in rebuilt[:400]:
        detail += "; the committed file carries a header the build does not emit"
    return [
        f"{BUNDLE.relative_to(ROOT)} does not match a rebuild from "
        f"{INPUT.relative_to(ROOT)} ({detail}) — run `npm run build:css` and commit the result, "
        "or explain the difference"
    ]


def main() -> int:
    problems = check_lockfile_agrees() + check_bundle_matches_a_rebuild()
    if problems:
        print(f"generated provenance: {len(problems)} artifact(s) do not match their build")
        for p in problems:
            print(f"  {p}")
        return 1
    if not _npm_available():
        print(
            "generated provenance: lockfile agrees with the manifest; the CSS rebuild "
            "was skipped because node_modules is absent (run `npm install` to include it)"
        )
        return 0
    print("generated provenance: the committed bundle is what its build command produces")
    return 0


if __name__ == "__main__":
    sys.exit(main())
