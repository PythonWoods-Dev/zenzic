---
description: "Walk through the z203-fatal-path-traversal fixture: a relative link escaping the docs directory into an OS system path, triggering the non-suppressible Z203 PATH_TRAVERSAL_FATAL and exit code 3."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z203 — Path Traversal (Fatal)

**Z-Code:** `Z203 PATH_TRAVERSAL_FATAL` · **Engine:** `standalone` · **Exit:** `3`

---

## The Fixture

One page containing a link that climbs out of the documentation tree.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Minimal standalone configuration |
| `docs/index.md` | Links to an OS system path via `../` traversal |

The offending line:

```markdown
- [Passwd](../../../../etc/passwd)
- [Encoded](..%2f..%2f..%2f..%2fetc%2fpasswd)
```

Four `../` segments from `docs/` reach the filesystem root, and the target is
`/etc/` — an operating-system directory, not project content. The second line
is the same destination with percent-encoded separators: `%2f` is a slash to
everything that resolves the link, so it arrives at the same file. The href is
decoded before it is classified, so both are `Z203`.

`Z203` is deliberately narrower than its sibling `Z202`. A link that merely
escapes `docs/` into another part of the repository is `Z202`. A link that
*lands* on a system directory is `Z203`, and carries its own exit code,
because the plausible explanations are all bad ones: a templating accident that
would publish a system path, or a deliberate probe.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z203-fatal-path-traversal
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 35 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'

docs/index.md:12  ✘  [Z203]  '../../../../etc/passwd' resolves outside the docs
directory

    10  │  ## Fatal Traversal Link
    11  │
    12  ❱  - [Passwd](../../../../etc/passwd) — this link escapes `docs/` and t…

docs/index.md:17  ✘  [Z203]  '..%2f..%2f..%2f..%2fetc%2fpasswd' resolves outside
the docs directory

    15  │  ## The Same Target, Percent-Encoded
    16  │
    17  ❱  - [Encoded](..%2f..%2f..%2f..%2fetc%2fpasswd) — `%2f` is a slash to …

Summary:  ✘ 2 security incidents  ✘ 0 errors  ⚠ 1 warning  💡 0 info  • 1 file
with findings
FAILED: Security incidents detected. Exit code 3 is mandatory.
DQS Final Score: 0/100 (Security Override — 2 non-suppressible findings
detected)
```

Read the summary line carefully: **0 errors**, and two *security incidents* —
one destination, two spellings. `Z203` is counted in its own class, which is
what routes the run to exit 3 instead of exit 1.

---

## Interpreting the Output

- **Severity:** `Error`, reported as a security incident.
- **Impact:** The score is forced to **0/100** regardless of everything else in
  the repository. The code's own penalty is `0.0` because no arithmetic is
  involved — the override replaces the score rather than deducting from it.
- **Suppressible:** **No.** Not by inline comment, not by directory policy, not
  by `--exit-zero`. This is inviolable by design.
- **Auto-Fixable:** No.

Zenzic never opens the traversed path. The finding is raised from resolving the
link, not from reading `/etc/passwd`.

---

## Resolve the Issue

There is no configuration change that resolves this one — that is the point.
Remove the traversal, or point the link at real project content:

```markdown
- [Configuration Reference](../reference/configuration-reference.md)
```

Re-run `zenzic check all`; the score returns to its normal calculation and the
run exits 0 or 1 on its remaining findings.

---

## See Also

- [Z202 — Path Traversal](z202-path-traversal) — traversal that escapes `docs/`
  without reaching a system directory; exit 2, also non-suppressible.
- [Z201 — Credentials](z201-credentials) — the other exit-code-2 security class.
- [Exit Codes](../../../reference/cli) — the full 0/1/2/3 contract.
