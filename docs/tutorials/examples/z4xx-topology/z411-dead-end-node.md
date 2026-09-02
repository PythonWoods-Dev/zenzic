---
description: "Walk through the z411-dead-end-node fixture: a reachable page with no outgoing links, forming a structural dead end and triggering Z411 DEAD_END_NODE."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z411 — Dead End Node

**Z-Code:** `Z411 DEAD_END_NODE` · **Engine:** `zensical` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

Pages a reader can arrive at and cannot leave.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Declares the engine and one per-file suppression |
| `docs/index.md` | Links to `deadend.md` |
| `docs/deadend.md` | Reachable, but links nowhere |
| `docs/secret.md` | Neither reachable nor linking out |
| `docs/suppressed_deadend.md` | A dead end that is deliberately allowed |

`Z411` is the outbound half of the topology pair. A page satisfies it by linking
somewhere — anywhere. `deadend.md` links nowhere, so a reader who follows the
site into it has only the back button.

The fixture also demonstrates the escape hatch. `docs/suppressed_deadend.md` is
just as much a dead end, and reports nothing, because the config says so:

```toml
[governance.per_file_ignores]
"docs/suppressed_deadend.md" = ["Z411"]
```

Some pages are legitimately terminal — a changelog, a licence, a glossary. The
declaration makes that a recorded decision rather than an unexplained silence.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z411-dead-end-node
uvx zenzic check all
```

Expected output:

```text
docs/deadend.md  ⚠  [Z402]  Physical file not listed in navigation.
docs/deadend.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/deadend/'
docs/deadend.md:1  ⚠  [Z502]  Page has only 16 words (minimum 50).
docs/index.md:1  ⚠  [Z502]  Page has only 8 words (minimum 50).
docs/index.md:3  ✘  [Z103]  'deadend.md' resolves to '/deadend/' which exists on
docs/secret.md  ⚠  [Z402]  Physical file not listed in navigation.
docs/secret.md:1  ⚠  [Z410]  Document is isolated and unreachable from defined
docs/secret.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
```

Note `suppressed_deadend.md` is absent from the output entirely — the per-file
ignore is working.

**This fixture exits `1`, and not because of `Z411`.** The `Z103` on
`docs/index.md:3` is an error-severity finding: the fixture's nav does not list
`deadend.md`, so the link into it is an orphan link. `Z411` itself is a warning
and would exit `0` on its own, as it does in the `Z410` fixture next door.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **5.0 DQS points** (structural category).
- **Auto-Fixable:** No. Zenzic cannot invent a useful onward link.

A dead end is a weaker signal than an unreachable page. Terminal pages are
sometimes correct, which is why the per-file suppression exists and why the
finding is a warning rather than an error.

---

## Resolve the Issue

**Add a genuine onward link** — a "see also", a link back to the section index,
a next-step pointer. The goal is a reader with somewhere to go, so a link added
purely to clear the finding misses the point.

**Or declare the page terminal**, as the fixture does for
`suppressed_deadend.md`. Use this where the page really is an endpoint.

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z410 — Unreachable Graph Node](z410-unreachable-graph-node) — the inbound
  half of the same topology check.
- [Z103 — Orphan Link](../z1xx-links/z103-orphan-link) — the error this fixture
  also raises, and why it exits 1.
- [Checks Reference](../../../reference/checks) — full rule specification.
