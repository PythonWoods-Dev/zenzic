---
description: "Architectural Decision Record defining what each .claude/ directory is for and the one-owner rule for facts."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 094: Control Plane Structure

---

## Context

The AI control plane under `.claude/` grew by accretion: each new agent, skill, reference
file and tracking ledger was added where it was convenient at the time. The result was a
tree in which the same fact lived in several files (a target count in a rule, an agent
definition and the top-level instructions; a rule's operational obligations in both the
rule file and `CLAUDE.md`), in which stable architectural references sat beside mutable
ledgers under one directory name, in which slash commands existed as two mechanisms that
shadowed each other, and in which inbound directives and outbound handoffs — the two halves
of one human channel — lived in different trees. Every one of these produced a real defect:
counts that disagreed, an obligation edited in one place and not the other, a command whose
file was never reached because a same-named skill took precedence.

---

## Decision

`.claude/` is organised by three questions, and every file answers exactly one of them:

| Question | Directory | Contents |
| :--- | :--- | :--- |
| **Who** acts? | `agents/` | Sub-agent definitions, in three families named by first segment: `gate-*` blocks a change, `lens-*` audits one target from one angle, `editorial-*` produces or classifies prose. |
| **How** is work done? | `skills/` | Every slash command. Human-gated workflows carry `disable-model-invocation: true`; nothing else distinguishes a gate from a formatter. |
| **What is true?** | `references/` and `state/` | `references/` holds what is stable between directives — invariants, rules, contracts, the catalog. `state/` holds what changes as work proceeds — the priority table, ledgers, staged memos. |

`CLAUDE.md` is an index into those three, not a fourth copy of their contents. Inbound
directives live with the outbound handoffs under `.human/`, which is private by
construction.

**A number lives in one file; everything else points to it.** A count, a range, a list of
targets, a rule's obligations — each has exactly one owning file, and every other mention
is a reference to that file, never a restatement of the value.

---

## Rationale

The three-question split makes placement a decision rather than a habit: a file that
answers "who" is an agent, one that answers "how" is a skill, and one that answers "what is
true" is either a reference or state depending on whether the answer changes between
directives. The alternative — organising by history, or by which directive introduced a
file — is what produced the accretion.

Splitting `references/` from `state/` on mutability matters because the two are read
differently. References are anchored at session start and treated as law; state is
consulted and updated as work proceeds. A mutable ledger under `references/` is either
read as law when it is not, or ignored as noise when the references beside it are not.

The one-owner rule for numbers is the mechanism behind the rest. Duplicated facts do not
drift on the day they are copied; they drift when one copy is edited, and the copy that
was not edited then reads as an independent confirmation. A pointer cannot drift, and a
reader who follows it always lands on the current value.

---

## Invariants

- A file is placed by the question it answers, never by when or why it was added.
- No numeric fact — a count, a range, a list of targets — is stated in more than one file
  under `.claude/`; secondary mentions are references to the owning file.
- `references/` contains only what is stable between directives; anything updated as a
  matter of course during work belongs in `state/`.
- Slash commands exist in exactly one mechanism, `skills/`; a human-gated workflow is
  marked by `disable-model-invocation: true` in its frontmatter.
- Adding a new top-level directory under `.claude/` requires a Tech Lead decision, an
  amendment to this record stating which of the three questions the directory answers (or
  why a fourth is needed), and a new row in the catalog's naming table before the first
  file is placed there.

---

## Consequences

- Reading the control plane costs three questions, not a tour of its history.
- A correction is made once. The shared lens protocol, the single copy of Rule 15's
  obligations and the catalog's naming table are the first beneficiaries.
- `CLAUDE.md` is short enough to be read rather than skimmed, at the cost of requiring the
  first-step reads it points to.
- Anything that wants to be a fourth top-level category has to argue for it in writing,
  which is the intended friction.
- The public half of the control plane — `references/`, `agents/`, `skills/` and
  `CLAUDE.md` — describes a constitution and its tooling; `state/` and `scripts/` are the
  working diary and stay private with `.human/`. Publication of the former does not imply
  the latter.
