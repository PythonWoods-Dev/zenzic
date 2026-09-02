---
description: "Design rationale of the Zenzic Privacy Gate — the fail-closed Zero-Trust security model spanning the Z2xx finding family."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Privacy Gate Architecture

The Privacy Gate is the security contract that prevents documentation pipelines
from publishing sensitive material. It is intentionally designed as a
**fail-closed** system.

In practical terms: when a security-class condition is detected, Zenzic stops
the pipeline immediately instead of producing a "best effort" report.

---

## Why the Gate Exists

Traditional documentation QA focuses on correctness (broken links, missing
anchors, structural drift). Privacy risk is different:

- A leaked credential can become an active incident within minutes.
- A traversal or forbidden-term disclosure can expose internal topology,
  policies, or regulated information.
- "Warning-only" behavior is incompatible with Zero-Trust governance.

The Privacy Gate therefore treats security findings as **operational blockers**,
not style issues.

### It is not only about attackers

A common objection is that this severity only makes sense for multi-tenant
production, where an adversary can reach your content. That reads the risk too
narrowly.

The realistic path to a leaked key in a documentation repository is not an
attacker. It is a contributor pasting a real value into an example while
debugging. It is a page copied in from an external source and never re-read, a
generated fixture that captured a live environment, or a snippet sanitised
everywhere except one line.

None of these require a hostile party. All of them are invisible in review
because the surrounding content looks innocuous — a documentation page is the
last place a reader expects a credential, which is exactly why one survives
there.

The same holds for a path traversal in a link. It rarely arrives as an attack;
it arrives as a templating accident, a relative path that was correct before a
file moved, or a copied snippet from a shell script. The finding is worth an
exit code either way, because the published site resolves the link identically
whatever the author intended.

So the gate protects against **inattention and misplaced trust first, and
deliberate attack second**. That ordering is why the security tier is
non-suppressible: a mechanism for silencing it would be used, overwhelmingly, on
the findings that were real and looked like noise.

---

## Zero-Trust Enforcement Model

The architecture follows four invariants:

1. **No trust in author intent.** Security checks run on every scan path.
2. **No suppression for security class.** Security findings are factual
    assertions, not advisory lint.
3. **Deterministic failure semantics.** Exit behavior is stable and auditable.
4. **CI-first containment.** The merge/deploy path is interrupted before
    publication.

This makes the Privacy Gate compatible with regulated pipelines where evidence
and reproducibility are mandatory.

---

## Architectural Scope

The Privacy Gate is not a single rule: it is a family-level control spanning
the Z2xx security domain in the Z-Code Gallery.

- [Z201 (Credential Secret)](../reference/finding-codes.md#z201)
- [Z202 (Path Traversal)](../reference/finding-codes.md#z202)
- [Z203 (Path Traversal Fatal)](../reference/finding-codes.md#z203)
- [Z204 (Forbidden Term)](../reference/finding-codes.md#z204)
- [Z205 (Forbidden Scheme)](../reference/finding-codes.md#z205)

For technical signatures, examples, and remediation playbooks, use the
[Z2xx Security family in the Finding Codes Gallery](../reference/finding-codes.md#z201).

---

## Operational Philosophy

The Privacy Gate enforces a strict distinction:

- **Quality findings** can be triaged and scheduled.
- **Security findings** must be removed or explicitly remediated before release.

This is the core Zero-Trust posture of Zenzic in CI/CD:
**documentation is treated as production attack surface**.
