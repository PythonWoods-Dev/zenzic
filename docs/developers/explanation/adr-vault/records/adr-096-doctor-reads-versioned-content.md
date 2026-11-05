---
description: "Architectural Decision Record moving zenzic doctor's boundary from a refusal of two folder names at config load to a check that a configured path is tracked by Git."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 096: The Doctor Reads Versioned Content

This document records what the doctor's path boundary protects, why it is expressed without naming any folder, where
the check lives, and how it behaves in the three places it can run.

**Status:** Accepted
**Decider:** The project owner
**Date:** 2026-11-05

---

## Context

Since `zenzic doctor` was introduced, the configuration model refused a `[doctor]` path that passed through two folder
names written in the product. The commit that added it gave the reason: a check reading them "would pass for whoever
holds those files locally and be unrunnable in CI or a fresh clone".

That reason is a product invariant, and it does not depend on any name. The refusal covered two names and left every
other untracked folder open, and it needed the product to name folders that are no concern of its users.

Asking `git check-ignore` was considered and refused. A folder may be excluded by a clone's own `.git/info/exclude`,
which no other clone has: measured on 2026-11-05, such a path passes on a fresh clone and in CI, where the check matters,
and `site/` or `build/`, ignored everywhere, would be refused for no reason. Refusing every folder whose name starts with
a dot was refused too: it rejects `.github/`, a legitimate versioned path.

---

## Decision

The invariant is stated directly: **the doctor's verdict must not depend on the clone, so a path it reads must be
versioned.**

- **Loading the configuration needs no Git.** The model refuses only what leaves the repository: an absolute path, or
  one with `..`.
- **The check lives in the doctor.** `tracked-paths` reports a configured path that exists and that Git does not track.
- **The core stays pure.** `check_tracked_paths` receives the list of tracked files. The CLI asks Git for it, with fixed
  arguments, as `zenzic guard` already does, so [ADR 002](./adr-002-zero-subprocesses.md) still holds for the core.

| Where it runs | A configured path Git does not track | Exit code |
| :--- | :--- | :--- |
| A clone that holds it | `tracked-paths` reports that it is not tracked | 1 |
| A fresh clone, or CI | absent: `adr-citations` reports the vault as not found | 1 |
| Outside a repository, or without `git` | nothing to compare with: `tracked-paths` reports nothing | as the other checks say |

---

## Rationale

The first two rows give the same answer, a finding, which is what the invariant asks for. The third is not a weakening:
without a repository there is no other clone for the verdict to differ from.

---

## Consequences

- A `[doctor]` path through a folder that used to be refused now loads, and `zenzic doctor` exits `1` with a finding. The
  CHANGELOG says so under «Changed».
- `zenzic doctor` runs one `git ls-files` when Git is there.
- A redirects file absent in a fresh clone stays silent, since its absence is not a finding; the clone that holds it
  untracked is told.
