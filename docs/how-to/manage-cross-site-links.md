---
description: "How to manage Z105 ABSOLUTE_PATH when your documentation spans multiple Zensical instances, and when to use inline ignores instead."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Manage Cross-Site Links

When your project hosts more than one Zensical instance under the same
domain (for example a User area at `/docs/` and a Developer area at
`/developers/`), links that cross instance boundaries **must use URL links**
(root-relative `/developers/…` or a full URL) instead of relative Markdown
file paths. Zensical does not resolve relative file-path links across plugin
boundaries — and neither does Zenzic's link validator.

By default, Zenzic's `Z105 ABSOLUTE_PATH` rule rejects any absolute link
(`/foo/bar`) because absolute paths break when a site is hosted in a
subdirectory. This guide shows you how to declare the cross-instance
prefixes your project legitimately owns, so the validator stops flagging
them — without weakening Z105 elsewhere.

---

## TL;DR — Which tool, when?

| Situation | Use this | Don't use |
|---|---|---|
| One isolated line in one file legitimately matches a rule | `<!-- zenzic:ignore: Zxxx -->` (or `<!-- zenzic:ignore: Zxxx -->` for Markdown) | — |
| Multiple cross-plugin links in different files | Inline ignores — one per link | — |

The decision rule: **if it is a property of one line, it belongs inline.**

---

## Cross-Instance Prefix Handling

!!! danger "`[link_validation]` removed"
    The `[link_validation]` TOML schema — including `absolute_path_allowlist` — is unsupported and raises a TOML validation error at startup. A `.zenzic.toml` that still declares `[link_validation]` must be updated.

    For cross-instance links that Z105 flags, use inline ignores at each affected line.

---

## When to use an inline ignore instead

Inline ignores are surgical. Reach for them when:

- A single line in a single file legitimately triggers a rule (e.g. a
  documentation example that *looks* like a credential but is fake).
- The exception is local context, not a project-wide truth.

```markdown
<!-- zenzic:ignore: Z2XX -->
api_key = "sk_test_PLACEHOLDER_FOR_DOCS"
```

```html
<!-- zenzic:ignore: Z1XX -->
[Hard link example](/legacy/path)
```

The inline form leaves an audit trail at the exact line — visible in PR
diffs, traceable in `git blame`.

---

## Anti-pattern: over-using inline ignores

Do **not** add `<!-- zenzic:ignore: Z1XX -->` as a blanket suppression. This:

- Implies the link is "broken and accepted" when in reality it is
  correct by design.
- Hides the cross-instance dependency from PR reviewers.

Annotate inline ignores with a comment explaining why the link is legitimately absolute,
so the suppression is traceable in `git blame`.

---

## Reverting

Remove an inline ignore and Z105 enforcement returns immediately on that line. There is no
migration cost.

---

## Related

- [Suppression Policy](../reference/suppression-policy.md) — Full reference for all suppression levels.
