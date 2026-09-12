---

description: "The Sovereignty Oath of Zenzic, declaring a zero-lock-in and zero-residue decommission policy."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# The Sovereignty Oath: Zero Residue

> *"Zenzic is a static analyzer in your pipeline, not a chain. The ability to remove it
> is not a failure mode — it is a design requirement."*

---

## The Oath

Zenzic makes one unconditional promise: **it will never hold your codebase hostage.**

To ensure the integrity of the Privacy Gate, Zenzic's audit core is strictly read-only.
We believe that a document integrity engine should never be a source of unintended mutations. Any future
remediation features will be implemented as explicit, interactive utilities
(e.g. `zenzic fix`), keeping the analysis phase 100% mutation-free.

This document is the formal commitment of that promise.

---

## 1. Zero Residue Guarantee

When you remove Zenzic, what remains?

| Component | Residue After Removal |
| :--- | :--- |
| **Your source files** | Unchanged — Zenzic never writes or modifies content |
| **Your application code** | Unchanged — Zenzic is never imported at runtime |
| **Your Python types** | Unchanged for the vast majority of users — built-in engines (MkDocs, Zensical, `standalone`/`prebuilt`/`vsm`) need no custom Python code at all. If you wrote a custom adapter, it subclasses `BaseAdapter` (see below) — removal means deleting that one small file, not unwinding an inheritance chain through your application code |
| **Your config format** | Standard `[tool.zenzic]` PEP convention — remove the section, done |
| **Your CI pipeline** | One workflow step — delete it |
| **Your pre-commit hooks** | One hook entry — remove it |

**Total removal time: 30 seconds.**

No migration scripts. No data format to convert. No architecture to unwind.

---

## 2. The Adapter Contract: Narrow, Not Invasive

Zenzic's adapter system is a runtime-enforced `BaseAdapter` contract
(`zenzic.core.adapters.BaseAdapter`, an `abc.ABC` — hardened from an earlier
structural `typing.Protocol` design under ADR-078-STRICT) — not free-form
duck-typing.

```python
from abc import abstractmethod
from zenzic.core.adapters import BaseAdapter

class MyEngineAdapter(BaseAdapter):
    def get_nav_paths(self) -> frozenset[str]: ...
    def get_metadata_files(self) -> frozenset[str]: ...
    def get_route_info(self, rel: Path) -> RouteMetadata: ...
    # ... every other @abstractmethod on BaseAdapter; Python refuses to
    # instantiate the subclass if any are missing.
```

**What this means for you:**

- If you use a **built-in engine** (MkDocs, Zensical, or `standalone`/`prebuilt`/`vsm`),
  you never touch this contract — there is no custom Python code, no class, nothing
  to subclass. The 30-second removal above is exact for you: delete the config
  section, delete the CI step, done.
- If you write a **custom adapter** (see [Writing an Adapter](../../how-to/implement-adapter.md)),
  your class does subclass `BaseAdapter` — a real, nominal inheritance relationship.
  Removing the `zenzic` dependency would break that one file's import.
- The blast radius of that break is exactly one file. A custom adapter is a small,
  single-purpose class whose only job is answering Zenzic's own questions about your
  docs layout — it is never imported by your documentation site's runtime, and it
  carries none of your application logic. Deleting it is the same order of effort as
  removing a CI workflow step, not an inheritance chain woven through your codebase.

The contract itself stays narrow by design: it only asks where your docs live and
how they route, nothing about your content, your build pipeline, or your
application code. If Zenzic is removed, your documentation site and your
application are both unaffected — the only thing that stops working is the adapter
file, and it was never doing anything except talking to Zenzic.

---

## 3. PEP-Compliant Configuration

Zenzic configuration lives in the `[tool.zenzic]` section of `pyproject.toml` —
the standard [PEP 518](https://peps.python.org/pep-0518/) location for tool config:

```toml title="pyproject.toml"
[tool.zenzic]
docs_dir = "docs"
engine = "mkdocs"
```

Or in a standalone `.zenzic.toml` at the repository root.

**Removal procedure:**

```toml title="pyproject.toml (after)"
# [tool.zenzic] section deleted — no other changes needed
```

Or:

```bash
rm .zenzic.toml
```

The `[tool.zenzic]` section is an isolated namespace. Removing it does not affect
any other tool configuration. No cascading effects. No shared state.

---

## 4. The Decommissioning Process

Removing Zenzic from a project is designed to be trivial and leave no residual lock-in. For step-by-step instructions on decommissioning, see the [Install & First Run guide — Decommissioning Zenzic](../../../how-to/install.md#decommissioning-zenzic).

---

## 5. Why We Document the Exit

Trust is built on the **ability to leave**, not the requirement to stay.

A tool that makes departure difficult is not confident in its value — it is protecting
its own presence. The Zenzic trust model is Zero-Trust: including toward Zenzic itself.

The analyzer exists to protect your documentation. Not to protect itself.
