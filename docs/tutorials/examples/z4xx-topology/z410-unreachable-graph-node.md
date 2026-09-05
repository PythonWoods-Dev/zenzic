---
description: "Walk through the z410-unreachable-graph-node fixture: a page that exists on disk but no navigation entry point reaches, triggering Z410 UNREACHABLE_GRAPH_NODE."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z410 — Unreachable Graph Node

**Z-Code:** `Z410 UNREACHABLE_GRAPH_NODE` · **Engine:** `zensical` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

A page that exists, builds, and cannot be reached.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Declares the `zensical` engine |
| `zensical.toml` | The navigation tree — lists `index.md` only |
| `docs/index.md` | The single entry point |
| `docs/secret.md` | Exists on disk; no nav entry, no inbound link |

`docs/secret.md` is a real, valid Markdown file. It renders. Its URL resolves if
you type it. What it does not have is any path from an entry point: the nav does
not list it, and no other page links to it.

This is the check that needs a graph. A per-file linter reads `secret.md`, finds
nothing wrong, and is correct — the defect is not *in* the file, it is in the
file's relationship to everything else. Only a tool holding the whole site's link
structure at once can see that nothing points here.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z410-unreachable-graph-node
uvx zenzic check all
```

Expected output:

```text
zensical • 2 files (2 pages, 0 assets) • 0.1s • 39 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:1  ⚠  [Z502]  Page has only 6 words (minimum 50).
docs/secret.md  ⚠  [Z402]  Physical file not listed in navigation.
docs/secret.md:1  ⚠  [Z410]  Document is isolated and unreachable from defined
entry points: '/secret/'
docs/secret.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/secret/'
docs/secret.md:1  ⚠  [Z502]  Page has only 14 words (minimum 50).

Summary:  ✘ 0 errors  ⚠ 6 warnings  💡 0 info  • 2 files with findings
```

Six findings from a two-file fixture. Only the `Z410` on `secret.md` is the
subject here — the `Z402` beside it reports the same fact from the navigation's
side, the `Z411`s are the dead-end check, and the `Z502`s note that these
minimal fixture pages are short. A real repository rarely shows this much
overlap; a two-page fixture triggers everything at once.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **5.0 DQS points** (structural category) — tied with
  `Z411` for the heaviest warning penalty.
- **Auto-Fixable:** No. Zenzic cannot know where in the navigation the page
  belongs, or whether it should exist at all.

`Z410` and `Z411` are complementary, not duplicates. `Z410` asks *can anything
reach this page*; `Z411` asks *can this page reach anything*. `secret.md` fails
both, which is why it appears twice.

---

## Resolve the Issue

Three outcomes, all legitimate:

1. **Add it to the navigation** if the page belongs in the site.
2. **Link to it** from a page that is already reachable.
3. **Delete it** if it is a leftover — which is often what an unreachable page
   turns out to be.

If the page is deliberately excluded from nav but must still be link-checked —
versioned reference material, for instance — declare that in `.zenzic.toml`
rather than leaving the finding to be ignored:

```toml
[governance.directory_policies]
"docs/secret.md" = ["Z410"]
```

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z411 — Dead End Node](z411-dead-end-node) — the same graph, examined in the
  opposite direction.
- [Z402 — Orphan Page](z402-orphan-page) — the navigation-side view of the same
  condition.
- [Checks Reference](../../../reference/checks) — full rule specification.
