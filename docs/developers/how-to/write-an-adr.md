<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Write an Architectural Decision Record

Zenzic records every significant technical decision as an ADR. `zenzic adr new` scaffolds
one so the numbering and structure are consistent without anyone having to remember them.

```bash title="Terminal"
zenzic adr new "Adopt RE2 for pattern matching"
```

```text
Created docs/developers/explanation/adr-vault/records/adr-094-adopt-re2-for-pattern-matching.md
Fill in Context, Decision, Rationale, Invariants and Consequences, then register it in the
vault index.
```

---

## Why the Number Is Allocated, Not Counted {#numbering}

The next number is one past the **highest identifier present**, not the number of records
in the vault. Those differ: the vault has genuine gaps where decisions were withdrawn or
numbers reserved and never used.

Filling a gap would be actively harmful. Citations live in code comments and prose across
the repository, and they refer to a decision by number. Reusing a gap silently repoints
every existing citation of that number at a different decision — a defect nothing would
surface, because the citation still resolves.

For the same reason, creating a second record with a number already in use is refused
rather than allowed alongside the first.

---

## What the Scaffold Writes {#skeleton}

The five canonical sections, an SPDX header, and a description in the frontmatter:

| Section | What belongs there |
| :--- | :--- |
| Context | Why the problem existed, and what forced a decision. |
| Decision | What was chosen, in a sentence or two. |
| Rationale | Why this option rather than the alternatives considered. |
| Invariants | What must never change as a consequence. |
| Consequences | What it costs, and what it makes possible. |

Two steps remain manual and deliberately so: writing the record, and registering it in the
vault index. Neither is mechanical.

---

## After Writing It {#verify}

Cite the ADR wherever the decision is enforced, then confirm the citation resolves:

```bash title="Terminal"
zenzic doctor
```

`doctor`'s `adr-citations` check reports any citation naming a record that does not exist,
so a typo in a number is caught in the same pass that checks the rest of the repository.

---

## Related Documents

* [`zenzic adr new` CLI reference](../../reference/cli.md) — Arguments and behaviour.
* [Check Repository Health](../../how-to/check-repository-health.md) — Verifying citations resolve.
* [ADR Vault](../explanation/adr-vault/index.md) — The existing corpus.
