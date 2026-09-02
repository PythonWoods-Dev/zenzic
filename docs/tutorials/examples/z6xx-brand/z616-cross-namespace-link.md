---
description: "Walk through the z616-cross-namespace-link fixture: a page in docs/public links into docs/internal, a boundary declared forbidden in [policies].cross_namespace_restrictions, triggering Z616 CROSS_NAMESPACE_LINK_FORBIDDEN."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z616 — Cross-Namespace Link Forbidden

**Z-Code:** `Z616 CROSS_NAMESPACE_LINK_FORBIDDEN` · **Engine:** `standalone` · **Exit:** `1`

---

## The Fixture

Two namespaces, and a link that crosses between them in the direction the project
forbids.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Declares the boundary under `[policies.cross_namespace_restrictions]` |
| `docs/public/index.md` | Public page that links into the internal namespace |
| `docs/internal/secret.md` | The internal page being linked to |

The policy is a single line:

```toml
[policies.cross_namespace_restrictions]
"docs/public" = ["docs/internal"]
```

Read it as: *pages under `docs/public` may not link to anything under
`docs/internal`.* The restriction is directional — the reverse link is allowed,
because an internal page referencing public material leaks nothing.

`docs/public/index.md` violates it on line 3:

```markdown
For secret details, see [Internal Secret Spec](../internal/secret.md).
```

Both files exist and the link resolves. This is not a broken link — it is a link
that works and should not.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z616-cross-namespace-link
uvx zenzic check all
```

Expected output:

```text
standalone • 2 files (2 pages, 0 assets) • 0.1s • 38 files/s

docs/public/index.md:3  ✘  [Z616]  Internal link '../internal/secret.md' from
namespace 'docs/public/index.md' targets forbidden namespace
'docs/internal/secret.md' (forbidden boundary 'docs/internal'). Declared in
[policies].cross_namespace_restrictions.
    1  │  # Public Index
    2  │
    3  ❱  For secret details, see [Internal Secret Spec](../internal/secret.md).

Summary:  ✘ 1 error  ⚠ 0 warnings  💡 3 info  • 1 file with findings
FAILED: Hard errors detected. Exit code 1 is mandatory.
```

---

## Interpreting the Output

- **Severity:** `Error`
- **Impact:** Deducts **8.0 DQS points** (brand category) — the heaviest penalty
  of any single finding code.
- **Auto-Fixable:** No. Zenzic cannot know whether the correct fix is removing
  the link, moving the target, or widening the policy.

The message names all three things you need: the source namespace, the target
namespace, and the boundary rule that was violated. The penalty is deliberately
severe because this finding class is a governance leak, not a formatting defect —
a public page pointing at internal material is a problem whether or not the link
resolves.

---

## Resolve the Issue

Three legitimate fixes, in the order you should consider them:

1. **Remove the link.** If the public page should not reference internal
   material, delete the reference.
2. **Move the content.** If the referenced material is genuinely public, move it
   out of `docs/internal/` and update the link.
3. **Amend the policy.** If the boundary itself is wrong, change it in
   `.zenzic.toml` — deliberately, as a reviewed decision, not to silence a
   finding.

Re-run `zenzic check all` after any of the three; the finding clears.

---

## See Also

- [Z614 — Unapproved Domain](z614-unapproved-domain) — the same Zero-Trust
  posture applied to external domains rather than internal namespaces.
- [Checks Reference](../../../reference/checks) — full rule specification.
