---
description: "Walk through the z407-invalid-pattern fixture: mkdocs.yml declares not_in_nav with a pattern gitignore syntax cannot parse, triggering Z407 INVALID_ENGINE_PATTERN."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z407 — Invalid Engine Pattern

**Z-Code:** `Z407 INVALID_ENGINE_PATTERN` · **Engine:** `mkdocs` · **Exit:** `1`

---

## The Fixture

The fixture lives at `examples/z407-invalid-pattern/` in the Zenzic repository.
It uses the **MkDocs** engine.

`mkdocs.yml` declares `not_in_nav` with `[[:bad:]` — an unterminated POSIX
character class that gitignore syntax cannot parse:

```yaml title="examples/z407-invalid-pattern/mkdocs.yml"
site_name: My Project
not_in_nav: |
  [[:bad:]
nav:
  - Home: index.md
```

```toml title="examples/z407-invalid-pattern/.zenzic.toml"
docs_dir = "docs"
fail_under = 0

[build_context]
engine = "mkdocs"
```

`docs/archive.md` is the page the pattern was meant to declare out of nav.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z407-invalid-pattern
uvx zenzic check all
```

The run reports three findings: `Z407` for the unusable pattern, and `Z402`
plus `Z410` on `docs/archive.md` — the page the declaration failed to cover.

Exit code: `1`

---

## Interpreting the Output

MkDocs refuses to build with this configuration at all: `Invalid git pattern`,
`Aborted with a configuration error!`. Zenzic cannot do the same — aborting
would deny every other finding in the repository — so it reports the pattern
and finishes the scan.

The two findings on `docs/archive.md` are the point. Before `Z407`, they were
the *only* trace: the author declared the page out of nav, the declaration
silently did nothing, and `Z402` kept firing with no explanation. `Z407` names
the cause.

The penalty is **0.0**. The configuration is wrong, but no document is worse
for it, so the score moves only through the findings the broken declaration
failed to prevent.

---

## What Would Not Be Reported

A pattern that parses but matches nothing — `docs/[orphan.md`, say — is not a
`Z407`. It compiles to a literal string no file will ever equal, which from the
outside is indistinguishable from a pattern whose targets have all been fixed.
A declaration that silences nothing is reported as `Z620` instead.
