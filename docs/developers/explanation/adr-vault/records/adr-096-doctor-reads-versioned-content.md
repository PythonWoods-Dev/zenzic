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

- **Loading the configuration needs no Git.** The model refuses what leaves the repository or was never content: an
  absolute path, a drive or root on Windows, `..`, and `.git`.
- **The check lives in the doctor.** `tracked-paths` reports what a configured path holds here and the last commit does
  not. A clone gets the last commit, never the index; every Markdown record of a vault counts, because one tracked file
  does not clear a record the holder reads and a clone does not have; a link is reported by its own name, since its
  target is what would have to be versioned.
- **Nothing outside is read.** A redirects file the last commit does not hold is reported and not read, since its lines
  are echoed in findings, and one behind a link out of the repository is not read with or without Git. `zenzic adr new`
  does not write through such a link.
- **The core stays pure.** `check_tracked_paths` receives the list of tracked files. The CLI asks Git for it, so
  [ADR 002](./adr-002-zero-subprocesses.md) still holds for the core.
- **The scanned repository decides nothing.** The doctor can now run on a repository it does not trust, and a fixed
  command line does not constrain what a repository's configuration may run. So Git comes from an absolute entry of
  `PATH` that is not the current folder, and the question is `git ls-tree`, which reads objects and not the index, with
  `core.fsmonitor` off, `safe.bareRepository=explicit`, and no lazy fetch.

| Where it runs | A configured path Git does not track | Exit code |
| :--- | :--- | :--- |
| A clone that holds it | `tracked-paths` reports that it is not tracked | 1 |
| A fresh clone, or CI | absent: `adr-citations` reports the vault as not found | 1 |
| Outside a repository, or without `git` | nothing to compare with: `tracked-paths` reports nothing | as the other checks say |
| A Git that refuses for another reason | a `tracked-paths` finding with Git's first line | 1 |

---

## Rationale

The first two rows give the same answer, a finding, which is what the invariant asks for. The third is not a weakening:
without a repository there is no other clone for the verdict to differ from.

---

## Consequences

- A `[doctor]` path through a folder that used to be refused now loads, and `zenzic doctor` exits `1` with a finding. The
  CHANGELOG says so under «Changed».
- `zenzic doctor` runs one `git ls-tree` when Git is there, and reads the names as bytes from Git, whatever the locale.
- A vault staged and not yet committed is reported until it is committed: a clone would not have it. A path inside a
  submodule counts as tracked, though a clone without `--recurse-submodules` lacks it.
- A redirects file absent in a fresh clone stays silent, since its absence is not a finding; the clone that holds it
  untracked is told.
- `zenzic guard --staged` still runs `git` by name, on the commit its user is making: it is outside this decision.
