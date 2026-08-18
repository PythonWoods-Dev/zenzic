---

description: "ADR 009: The configuration follows the target, not the caller — preventing Context Hijacking."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 009: Path Sovereignty — Configuration Follows the Target

**Status:** Active
**Decider:** Architecture Lead
**Date:** 2026-04-12 (CEO-052)

---

## Context

`find_repo_root()` searches upward from `os.getcwd()` — the invoking
shell's current working directory. This worked correctly for the standard case
where the user runs Zenzic from inside the repository they want to analyse.

It failed for any scenario where the caller's working directory differed from the
target repository:

```bash
# CWD = /home/user/my-tools
# Target = /home/user/another-project/docs
zenzic check all /home/user/another-project/docs
```

In this case, `find_repo_root()` would walk upward from `/home/user/my-tools`,
find *that* repository's `.zenzic.toml`, and load *that* repository's
configuration — including its `engine`, `docs_dir`, `excluded_dirs`, and custom
rules. The analysis target was `another-project`, but the configuration applied
was from `my-tools`. This is **Context Hijacking**.

---

## Decision

> **"The configuration follows the target, not the caller."**

When an explicit `PATH` argument is provided to any filesystem-interacting CLI
command, `find_repo_root()` is called with `search_from=target_path` — walking
upward from the **target**, not the CWD:

```python
# core/scanner.py
def find_repo_root(
    search_from: Path | None = None,
    fallback_to_cwd: bool = False,
) -> Path:
    start = search_from or Path.cwd()
    for parent in [start, *start.parents]:
        if (parent / ".git").exists() or (parent / ".zenzic.toml").exists():
            return parent
    if fallback_to_cwd:
        return start
    raise RuntimeError(...)
```

`_apply_target()` in `cli/_target_resolver.py` orchestrates docs-root
recalibration after target resolution: it preserves configured `docs_dir` when
the target is the repo root, or patches `docs_dir` from the resolved target.

---

## The `_apply_target()` Invariant

When `target == repo_root` (the user points directly at a repo root, not a
subdirectory), `docs_dir` is **preserved from the config** rather than overridden
to `"."`. This prevents a subtle regression: a user running
`zenzic check all /path/to/repo` should respect that repo's `docs_dir = "docs"`
setting, not flatten it to the root.

```python
# _apply_target() — canonical logic
if resolved_target == repo_root:
    # Target IS the repo root: honour the config's docs_dir.
    docs_root = repo_root / config.docs_dir
else:
    # Target is a subdirectory: treat it as the docs root directly.
    docs_root = resolved_target
```

---

## Rationale

The technical rationale and architectural context driving this design decision are outlined below.

### 1. The Principle of Contextual Integrity

A configuration file belongs to the project it lives in. Loading a foreign
`.zenzic.toml` because of a coincidence of working directory is a **configuration
supply chain vulnerability** — the analysis is secretly governed by rules the
user did not intend to apply.

### 2. CI/CD Correctness

In CI pipelines, the working directory is often the runner's home, a workspace
root, or a tool directory — not the documentation repository. Path Sovereignty
ensures that `zenzic check all $DOCS_PATH` in CI always applies the correct
project-specific rules, regardless of the runner's `$PWD`.

### 3. Symmetry with ADR-007

ADR-007 (Sovereign Sandbox) established that the **scan scope** follows the
target. ADR-009 completes the picture: the **configuration** also follows the
target. Together they guarantee that every aspect of an analysis — what is
scanned, what rules apply, and what escapes are forbidden — is determined solely
by the target repository.

---

## Scope

Path Sovereignty applies to every CLI command that accepts an optional positional
`PATH` argument (Rule R18 — Total CLI Symmetry):

| Command | PATH semantics |
|---------|---------------|
| `zenzic check all [PATH]` | Sovereign root: `find_repo_root(search_from=PATH)` |
| `zenzic score [PATH]` | Same |
| `zenzic diff [PATH]` | Same; snapshot path derived from resolved `repo_root` |
| `zenzic init [PATH]` | Genesis Nomad: `PATH` is the `repo_root` directly; created if absent |
| `zenzic lab`, `zenzic inspect` | No PATH argument — exempt |

---

## Consequences

- Running Zenzic from any directory produces identical results to running it
  from inside the target repository — no surprises for CI operators.

- The `fallback_to_cwd=True` parameter of `find_repo_root()` is a constrained

    fallback path. Use it only where command semantics explicitly require a
    current-working-directory fallback, and avoid introducing it as a default in
    PATH-targeted command flows.
