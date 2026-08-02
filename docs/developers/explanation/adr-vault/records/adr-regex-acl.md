---

sidebar_position: -1
description: "ADR 013: Why Zenzic wraps google-re2 behind a Regex Anti-Corruption Layer to enforce ReDoS protection without degrading developer experience."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 013: The Regex Anti-Corruption Layer (ReDoS Protection)

**Status:** Accepted (May 2026)
**Decider:** Tech Lead
**Date:** 2026-05-10 (v0.8.x)

---

## Context

Zenzic adopted **RE2** to enforce the ZRT-007 security invariant: regular
expression evaluation in production must have predictable, linear-time
behaviour and must not expose the project to catastrophic backtracking
(**ReDoS**).

The problem is that Python's regex ecosystem is shaped around the standard
library `re` API, while `google-re2` is not a perfect drop-in replacement.
It is intentionally stricter and exposes a narrower surface:

- Some familiar constants and flags from `re` are not exported directly.
- Some stdlib regex constructs are forbidden because they are not regular
  languages or because they rely on backtracking semantics.
- Existing code across the core expected a `re`-shaped module surface
  (`compile`, `sub`, `finditer`, flags such as `DOTALL`, type hints such as
  `Pattern` and `Match`).
- A naive migration would spread `import re2` caveats through dozens of files,
  lowering readability and coupling the entire codebase to a leaky C-extension
  API.

A second, more dangerous temptation also appeared during implementation:
falling back to the stdlib `re` engine whenever RE2 rejected a pattern.
That fallback would have silently broken ZRT-007 at the exact point where the
security invariant matters most. A rejected pattern must fail hard, not be
quietly recompiled by a vulnerable engine.

The options examined were:

- **Option A** — Import `re2` directly everywhere and teach every module about
  its incompatibilities.
- **Option B** — Use `re2` when possible, but silently fall back to `re` for
  unsupported syntax.
- **Option C** — Introduce a small **Anti-Corruption Layer / Façade** that
  presents a `re`-like API to the rest of the core while strictly enforcing
  RE2 as the only runtime engine.

## Decision

We adopt **Option C**.

Zenzic introduces a dedicated module:

```python
from zenzic.core import regex as re
```

This module acts as a **Regex Anti-Corruption Layer**:

- it re-exports a `re`-shaped surface (`compile`, `search`, `match`, `sub`,
  `finditer`, `findall`, `escape`),
- it exposes familiar stdlib-style flags and exceptions for caller ergonomics,
- it centralizes the typing bridge (`RegexPattern`, `Match`) for Mypy,
- it translates compatible flag usage into RE2-safe compilation,
- it rejects unsupported constructs by raising immediately,
- it never falls back to stdlib runtime compilation.

The consequence is deliberate: **all production regex execution remains on
RE2, everywhere, always**.

Where legacy (pre-v0.8.x) patterns used stdlib-only constructs such as lookbehind, <!-- * zenzic:ignore: Z601 - ADR historical record * -->
lookahead, or other non-RE2 syntax, those patterns are rewritten into
RE2-compatible forms or the surrounding code is adjusted to perform the missing
semantic filtering outside the regex engine.

## Rationale

This decision preserves both sides of the contract that matter:

- **Security discipline.** ZRT-007 remains real, not aspirational. If a pattern
  is incompatible with RE2, the failure is immediate and visible.
- **Developer experience.** The rest of the codebase can keep using a stable,
  obvious API (`re.compile(...)`, `re.DOTALL`, `re.sub(...)`) without importing
  multiple helper symbols or encoding engine quirks in every module.
- **Containment of vendor mismatch.** `google-re2` is a valuable engine but an
  incomplete abstraction relative to Python's stdlib expectations. The ACL
  localizes that impedance mismatch to one file.
- **Typing integrity.** The bridge to `Pattern` / `Match` types is centralized
  instead of duplicated via repeated `TYPE_CHECKING` boilerplate.

Option A was rejected because it would spread C-extension friction everywhere:
import-order problems, repeated typing shims, and direct coupling to RE2's
incomplete Python surface.

Option B was rejected because it would destroy the purpose of the migration.
A security invariant that degrades silently under pressure is not an invariant.
It is theatre.

## Invariants

These constraints are permanent consequences of ADR-013:

1. **No stdlib fallback at runtime.** Unsupported patterns must raise. They may
   be rewritten, but they may not be recompiled by `re` in production code.
2. **All governed regex imports go through the ACL.** Production modules,
  contract tests, and repository quality tooling must use
  `from zenzic.core import regex as re` instead of importing `re` or `re2`
  directly.
3. **Typing stays centralized.** `RegexPattern` and `Match` aliases live in the
   ACL. The rest of the codebase must not replicate `TYPE_CHECKING` bridges.
4. **RE2 incompatibilities are solved structurally.** If a pattern uses
   lookbehind, lookahead, backreferences, or other unsupported constructs, the
   fix is to rewrite the pattern or move part of the logic into ordinary Python
   code.
5. **Warnings are treated as defects.** If the regex layer emits deprecation or
   compatibility warnings during tests, the implementation is incomplete.

## Consequences

The system impact and operational consequences resulting from this architectural decision include:

### Pros

- **ZRT-007 is enforceable in one place.** Auditability improves because there
  is a single choke point for regex semantics.
- **Core code stays readable.** Most modules continue to look like idiomatic
  Python instead of RE2-integration scaffolding.
- **Future migration cost drops.** If RE2 bindings change again, only the ACL
  should need adaptation.
- **Tests become more meaningful.** RE2 rejection tests now validate the real
  engine boundary rather than a mixed-engine runtime.

### Cons

- **The ACL must be maintained carefully.** It is now a critical boundary and
  cannot be treated as a trivial helper.
- **Some regexes become less compact.** Patterns that once relied on
  lookbehind/lookahead must sometimes be split into a regex pass plus semantic
  checks in Python.
- **Performance scrutiny increases.** Rewriting patterns away from advanced
  constructs can change hot-path behaviour and must be measured, not assumed.

## Anti-Corruption Boundary

The ACL exists because `google-re2` is both correct and incomplete relative to
what the rest of the Python ecosystem expects. The right response is not to let
that incompleteness leak into every caller. The right response is to absorb the
mismatch at the boundary.

That is exactly what an Anti-Corruption Layer is for:

- outside the boundary, the code speaks **Zenzic's language**;
- inside the boundary, the façade translates that language into the external
  engine's narrower contract;
- if translation is impossible, the boundary rejects the request explicitly.

This keeps the core coherent without weakening the security posture.

---

## Related

- [ADR 001: Lint the Source](./adr-lint-source.md) — content and source
  semantics must stay readable to humans.
- ADR 002: Zero Subprocesses Policy — the regex
  layer must remain in-process and deterministic. *(Maintainer Only)*
