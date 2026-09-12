---
description: "Analysis of the mdx-jsx-links fixture: a JSX component link that resolves, one that does not, and a Markdown link inside a JSX attribute that is text rather than a link. Z-Code Z101 LINK_BROKEN, exit 1."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# MDX & JSX Links

**Z-Code:** `Z101 LINK_BROKEN` · **Engine:** `standalone` · **Exit:** `1`

---

## Why This Fixture Is Not a Z101 Fixture

Every other scenario here demonstrates one code. This one demonstrates a
**surface**: what Zenzic does with JSX, which is the part of MDX a Markdown
fixture cannot show. The `Z101` is one of three constructs under test, and the
other two produce **no finding at all** — which is the harder half to believe
without seeing it, and the reason this has its own page rather than a paragraph
on [z101 — Broken Links](z101-broken-links).

A rule card shows you the syntax. A fixture shows you the behaviour, including
the behaviour of staying silent.

---

## The Fixture

The fixture lives in `examples/mdx-jsx-links/` in the Zenzic repository:

| File | Role |
| :--- | :---- |
| `docs/index.mdx` | Source — three JSX constructs, one of which is reported |
| `docs/guide.mdx` | The target that exists, so a resolving link has something to resolve to |
| `.zenzic.toml` | Engine: `standalone`, `fail_under = 0` |

The three constructs:

| Line | Construct | Reported |
| :--- | :--- | :--- |
| 16 | `<Link to="./guide.mdx">` — target exists | **No** — it resolves |
| 21 | `<Link to="./nowhere.mdx">` — target does not exist | **`Z101`** |
| 27 | `<Callout title="See [the guide](./nowhere.mdx) for details">` | **No** — a string, not a link |

`Link` is not a tag name Zenzic knows, and that is deliberate: the rule is that a
**capitalised** tag carrying `to`, `href` or `src` is a link. Component names are
unbounded, so a list of them would create a blind spot the day someone invents a
fourth; attribute names are where false positives live, so those are a fixed set.
A component carrying none of the three is not a link.

The `Callout` line is the false positive this release closed. MDX does not parse
Markdown link syntax inside a prop string — it reaches the page as literal text,
producing no anchor — so reporting it would be wrong.

---

## Running the Example

```bash
# Clone the Zenzic repository — no extra installation required
cd examples/mdx-jsx-links
uvx zenzic check references
```

Expected output:

```text
standalone • 2 files (2 pages, 0 assets) • 0.0s • 94 files/s

docs/index.mdx:21  ✘  [Z101]  './nowhere.mdx' resolves to '/nowhere/' which is
not in the Virtual Site Map — the target file may not exist

    19  │  Markdown link with the same target would be:
    20  │
    21  ❱  <Link to="./nowhere.mdx">A page that was never written</Link>
    22  │
    23  │  A Markdown link written inside a JSX string attribute. It renders as

────────────────────────────────────────────────────────────────────────────────

Summary:  ✘ 1 error  ⚠ 0 warnings  💡 2 info  • 1 file with findings

FAILED: Hard errors detected. Exit code 1 is mandatory.
```

Exit code: `1`

Or through the lab, which asserts the expectation rather than printing it:

```bash
zenzic lab mdx
```

---

## Interpreting the Output

One error, and **two silences that are results rather than omissions**. You can
check that they are real by deleting the constructs: removing the resolving
`<Link>` or the `Callout` raises the `Z101` count from one to two, which is how
the silence was measured rather than assumed.

- **Scan Type:** `Link Validator` (Virtual Site Map resolution)
- **Severity:** `Error`
- **Impact:** A component link to a non-existent page renders as a dead route in
  the built site exactly as a broken Markdown link does, so it is the same code.

---

## What This Fixture Deliberately Omits

There is no inline-suppression construct here. `data-zenzic-ignore` and
`<!-- zenzic:ignore: … -->` both work in `.mdx`, and so does the JSX comment form
`{/* zenzic:ignore: … */}` — with or without spaces inside the braces — but a
fixture that demonstrated one would need a second finding to suppress, and this
page is about link extraction. See [`Z603`](../../../rules/Z603.md) for the
suppression mechanics and the codes each mechanism covers.

---

## See Also

- [z101 — Broken Links](z101-broken-links) — the same code in plain Markdown.
- [MDX Support](../../../explanation/discovery.md#mdx) — which MDX constructs are
  understood, and which are deliberately out of scope.
- [z120 — Unknown HTML Attribute](z120-unknown-html-attr) — the HTML tag tier,
  which JSX components are exempt from.
- [Checks Reference](../../../reference/checks.md) — full rule specification.
