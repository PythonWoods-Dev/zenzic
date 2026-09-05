---
description: "Walk through the z617-forbidden-content fixture: prose matching an RE2 pattern in [policies].forbidden_content_patterns, triggering Z617 FORBIDDEN_CONTENT_PATTERN."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z617 — Forbidden Content Pattern

**Z-Code:** `Z617 FORBIDDEN_CONTENT_PATTERN` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

Prose containing a word the project has ruled out of published documentation.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Declares the forbidden patterns |
| `docs/index.md` | Contains the word `confidential` |

The policy is a list of RE2 patterns matched against document text:

```toml
[policies]
forbidden_content_patterns = ["(?i)confidential"]
```

The `(?i)` prefix makes it case-insensitive, so `Confidential` and `CONFIDENTIAL`
match too.

This is the general form of the terminology checks. `Z519` matches a word list;
`Z617` matches arbitrary patterns, which lets it catch shapes rather than
spellings — an internal hostname convention, a deprecated product name across
its variants, a classification marker that should never reach a public site.

It is not a credential scanner. Leaked secrets are `Z201`, are non-suppressible,
and exit 2. `Z617` is an editorial control, and its default-allow posture means
it only ever catches what a project thought to name.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z617-forbidden-content
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 25 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:3  ⚠  [Z617]  Content matches forbidden pattern
'(?i)confidential': 'confidential'. Declared in
[policies].forbidden_content_patterns.
    1  │  # Forbidden Content Example
    2  │
    3  ❱  This document contains confidential information.
```

The message reports both the pattern and the text it matched — necessary when a
pattern is general enough that the match is not obvious.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **2.0 DQS points** (brand category).
- **Auto-Fixable:** No. A replacement is an editorial decision.
- **Opt-In:** Yes — silent until `forbidden_content_patterns` is declared.

Patterns compile with RE2: no lookahead, no backreferences, and no catastrophic
backtracking regardless of what the pattern and the document do together.

---

## Resolve the Issue

Rewrite the prose, or narrow the pattern if it is over-matching. A pattern that
fires on legitimate uses gets suppressed everywhere, and a rule suppressed
everywhere protects nothing.

For a genuine exception:

```markdown
The confidential-computing enclave... <!-- zenzic:ignore Z617 -->
```

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z519 — Weasel Words](../z5xx-content/z519-weasel-words) — the word-list form
  of the same idea.
- [Z201 — Credentials](../z2xx-security/z201-credentials) — actual secret
  detection, non-suppressible and exit 2.
- [Checks Reference](../../../reference/checks) — full rule specification.
