---
description: "Walk through the z412-traceability-broken fixture: a spec page that no architecture document references, breaking a declared traceability contract and triggering Z412 TRACEABILITY_BROKEN."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z412 — Traceability Broken

**Z-Code:** `Z412 TRACEABILITY_BROKEN` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

A specification nothing in the architecture refers to.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Declares the traceability contract |
| `docs/specs/spec1.md` | A spec with no inbound architecture reference |
| `docs/architecture/index.md` | The namespace that should reference it |
| `docs/index.md` | Site entry point |

The contract is one line:

```toml
[policies]
traceability_targets = {"specs/**" = ["architecture/**"]}
```

Read it as: *every page under `specs/` must be referenced by at least one page
under `architecture/`.*

This inverts the usual direction of link checking. `Z101` asks whether a link's
target exists. `Z412` asks whether a *required* link exists at all — a document
can be perfectly well-formed and still violate it, because the defect is an
absence. A spec no architecture document cites is either unimplemented or
forgotten, and both are worth knowing before someone builds against it.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z412-traceability-broken
uvx zenzic check all
```

Expected output:

```text
standalone • 3 files (3 pages, 0 assets) • 0.1s • 60 files/s

docs/specs/spec1.md:1  ⚠  [Z412]  Document matches traceability target
'specs/**' but has no inbound references from required source namespaces
['architecture/**']

Summary:  ✘ 0 errors  ⚠ 1 warning  💡 5 info  • 1 file with findings
DQS Final Score: 96/100 (Gate Passed)
```

The message names the pattern the document matched and the namespaces that were
searched for a reference — enough to tell whether the spec is missing a citation
or the contract is aimed at the wrong namespace.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **4.0 DQS points** (navigation category).
- **Auto-Fixable:** No. Only an author knows which architecture document should
  cite this spec.
- **Opt-In:** Yes. `Z412` is silent until `traceability_targets` is declared —
  a repository without that policy never sees this finding.

`Z412` is also non-inline-suppressible: the finding is about a relationship
between two namespaces, so there is no single line in `spec1.md` where a
`zenzic:ignore` comment would sensibly live.

---

## Resolve the Issue

**Add the missing reference** from the architecture side:

```markdown
The ingestion pipeline implements [Spec 1](../specs/spec1.md).
```

**Or correct the contract** if the required namespace is wrong. Traceability
policies are easy to point at the wrong directory when a repository is
reorganised, and a policy matching nothing is worse than no policy.

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z616 — Cross-Namespace Link Forbidden](../z6xx-brand/z616-cross-namespace-link)
  — the mirror image: a link between namespaces that must *not* exist.
- [Z410 — Unreachable Graph Node](z410-unreachable-graph-node) — reachability
  from navigation rather than from a required namespace.
- [Checks Reference](../../../reference/checks) — full rule specification.
