---

sidebar_position: 3
description: "ADR 015: Zenzic validates its own DQS badge freshness natively via --check-stamp, eliminating the need for external git/bash gates in CI workflows."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 015: Native Telemetry Validation

**Status:** Active
**Decider:** Architecture Lead
**Date:** 2026-05-30

---

## Context

`zenzic score --stamp` writes the current DQS score as a Shields.io badge URL into any file
listed in `badge_stamp_files`. This mechanism is deterministic and Git-native: the badge is
crystallised in each commit, requiring no external service.

However, Zenzic has no native mechanism to **verify** that the committed
badge matched the computed score. The only enforcement path was an external bash gate added
manually to CI workflows:

```bash
# Typical pre-ADR-015 CI pattern
git diff HEAD --quiet README.md README.it.md || exit 1
```

This pattern had four structural defects:

1. **Hardcoded filenames** — the gate did not honor `badge_stamp_files`. A project configuring
   `README.it.md` as an additional stamp target had to update the CI script manually.
2. **Zero portability** — the gate required both `git` and `bash`. Non-bash CI environments
   and shallow clones introduced false passes.
3. **Undiscoverable** — first-time Zenzic users had no hint that this gate was required.
   The `--stamp` documentation described how to write badges; the enforcement was a tribal
   convention not surfaced by `zenzic --help`.
4. **Violated the Zero-Config Default pillar** — users who opted into badge stamping had to
   configure external CI infrastructure for a Zenzic-owned feature. The engine should own the
   full lifecycle of its own artefacts.

---

## Decision

> **Zenzic validates its own artefacts natively.** The `--check-stamp` flag computes the
> expected Shields.io URL for the current score, reads `badge_stamp_files` from configuration,
> and exits 1 with a precise, actionable error message if any configured file contains a stale
> badge URL.

The invariant: if both markers (`<!-- zenzic:audit-badge -->`, `<!-- zenzic:score-badge -->`) are absent from a file, `--check-stamp`
returns True (pass). The gate activates only when the user has explicitly opted into badge
stamping. No opt-out configuration is required from users who do not use badges.

`--stamp` (write) and `--check-stamp` (verify) are mutually exclusive. This prevents ambiguous
invocations and enforces the read/write boundary between the two modes.

---

## Rationale

The technical rationale and architectural context driving this design decision are outlined below.


### 1. Zero-Config Default enforcement

The Zero-Config Default pillar requires that users can adopt Zenzic features without configuring
external tooling. Under the pre-ADR-015 model, badge stamping was an Opt-In feature (user inserts
the marker) that secretly required a corresponding Opt-In in CI (user writes the `git diff` gate).
The second opt-in was invisible.

`--check-stamp` closes the loop: the user inserts the marker once, and Zenzic handles both
writing (`--stamp`) and verifying (`--check-stamp`) the badge. `zenzic-action` runs `--check-stamp`
automatically after `check all` (opt-out: `check-stamp: 'false'`). The default CI experience
is zero-configuration.

### 2. Config-aware gate

`--check-stamp` reads `badge_stamp_files` from `.zenzic.toml` — the same key that controls
`--stamp`. Adding a new file to `badge_stamp_files` automatically extends the freshness gate
to that file. No CI script edits, no `git diff README.it.md` additions.

### 3. Git-agnostic implementation

`_check_stamp_file(path, marker, expected_url)` reads the file from disk, locates the requested
marker using the same parser as `_stamp_file()`, extracts the badge URL via `_SHIELDS_URL_RE`,
and compares it to the expected URL. No subprocess, no `git diff`, no shell dependency.
The gate works in any environment where Python and the repository checkout are present.

### 4. Progressive disclosure

When `--check-stamp` detects a stale badge, the error names the specific file and prescribes
the exact remediation step:

```text
[FAILED] Badge (score) in README.md is stale. Run 'zenzic score --stamp' locally and commit the result.
```

The user receives a complete action: the problem, the file, and the fix — without reading
documentation.

---

## Invariants

- `_check_stamp_file(path, marker, expected_url)` returns **True (pass)** when:
  - The file does not exist.
  - The target marker is absent.
  - The marker is present but no Shields.io badge URL follows.
  - The badge URL matches `expected_url` exactly.
- `_check_stamp_file` returns **False (stale)** only when the marker is present and the badge
  URL differs from `expected_url`.
- `--stamp` and `--check-stamp` raise a fatal error if invoked together (mutual exclusion).
- `zenzic-action` skips `--check-stamp` when `ZENZIC_AUDIT=true` (audit mode produces no scored
  artefacts).

---

## Consequences

- The bash `_badge-freshness-check` recipe in `just verify` is replaced by a single native
  invocation: `zenzic score --check-stamp --no-header`.
- CI users of `zenzic-action` receive the badge freshness gate automatically without any
  workflow YAML change.
- The `badge_stamp_files` configuration key is now the single source of truth for both stamping
  and verification — no duplication between `.zenzic.toml` and CI scripts.
- The Zero-Config Default pillar is fully honored: badge stamping is plug-and-play from marker
  insertion to CI enforcement.

---

## Related

- [ADR 009: Path Sovereignty](./adr-path-sovereignty.md) — same principle applied to config path resolution.
- [ADR 005: Agnostic Universalism](./adr-agnostic-universalism.md) — portability as a first-class design constraint.
