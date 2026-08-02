---

description: "Overview of Zenzic's governance constitution, immutable pillars, and licensing standards."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Governance & Sovereignty

> *"Stability is not the enemy of progress. It is its precondition."*

This section is not documentation for bureaucrats. It is the **Engineering of
Stability** — a formal contract that protects the Three Pillars of the Privacy Gate
from erosion by convenience, urgency, or well-intentioned shortcuts.

---

## The Supreme Law: The Three Pillars

Every governance document in this section exists to defend one invariant:
**the Three Pillars are non-negotiable.**

| Pillar | Invariant | What Breaking It Would Cost |
| :---: | :--- | :--- |
| **I** | Lint the Source, Not the Build | Analysis of HTML output chains Zenzic to the build pipeline — the thing it is designed to precede. |
| **II** | Zero Subprocesses | A subprocess call escapes the trust boundary. It introduces a dependency Zenzic cannot audit, on an execution context it does not control. |
| **III** | Pure Functions First | Impure functions in hot-path loops are invisible failure modes. Determinism is the foundation of the trust model. Every finding must be reproducible. |

These are not design preferences. They are load-bearing walls. When the Three Pillars
hold, the Privacy Gate holds.

---

## Governance Documents

| Document | Purpose |
| :--- | :--- |
| [The Sovereignty Oath](./exit_strategy) | Proof that Zenzic is a tool, not a master. Zero Residue. Reversible in 30 seconds. |
| [Evolution Policy](./evolution_policy) | The formal process for evolving — or protecting — the Three Pillars. |
| [License Compliance](./licensing) | Apache-2.0 + REUSE 3.3. Every file carries the cryptographic signature of its license. |

---

## The Engineering of Stability

Governance documents are not written for today. They are written for the engineers
who will maintain Zenzic in 2030, under pressures that do not yet exist, facing
architectural temptations that have not yet been named.

The [ADR Vault](../adr-vault/index.md)
is the operational memory of the project. This Governance section is its
**constitutional layer** — the principles the Ledger itself cannot override.

---

## Abstract

Zenzic's governance system is designed around a single guarantee: that the rules of the
Privacy Gate do not change silently mid-voyage.

The Three Pillars — *Lint the Source*, *Zero Subprocesses*, *Pure Functions First* —
are Constitutional Laws, not architectural preferences. Changing any Pillar requires a
Major version increment and a formal stress-test review.

Zenzic's governance is built on three axes:

| Axis | Document | Guarantee |
| :--- | :--- | :--- |
| **Liberty** | [The Sovereignty Oath](./exit_strategy) | Removed in 30 seconds. Zero residue. Core is read-only. |
| **Duration** | [Evolution Policy](./evolution_policy) | No Pillar changes without a public constitutional process. |

This section is the **governance constitution** — the constraints that protect Zenzic's
own structure from erosion by convenience, urgency, and well-intentioned shortcuts.

### "Do not trust us. Trust the system we built to protect you."

This section details the specifications and guidelines for "Do not trust us. Trust the system we built to protect you." within the Zenzic ecosystem.

