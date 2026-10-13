<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Developer Troubleshooting

Quick reference for developer environment, release workflow, and Zenzic-block issues.
Each entry follows the pattern: **Symptom → Cause → Resolution**.

For user-facing installation and configuration problems, see the
[User Troubleshooting Guide](../../how-to/troubleshooting.md).

---

## Installation & Environment

Follow the setup instructions below to configure your development and scanning environment.

### `zenzic --version` shows the wrong version after a release bump

**Symptom:** The global `zenzic` command reports an older version than expected, even
after running `uv tool upgrade zenzic --force-reinstall`.

**Cause:** `uv tool` tracks the installation source set at first install time.
`--force-reinstall` refreshes packages but does not change the registered source path.
If the tool was originally installed from a different local clone (e.g.
`file:///home/user/dev/PythonSandbox/zenzic`), the upgrade re-builds from that stale
clone, not from the authoritative repository.

The output line `~ zenzic==0.24.x (from file:///path/to/wrong/repo)` confirms this condition.

**Resolution:** Reinstall the tool explicitly from the authoritative repository path:

```bash
uv tool install --reinstall 'zenzic @ file:///path/to/GithubProjects/zenzic'
```

Verify:

```bash
zenzic --version   # must match the bumped version
```

---

### Verification reports a missing core path (`ZENZIC_CORE_PATH` not found)

**Symptom:** `just verify` in `zenzic-doc` or `zenzic-action` fails with a message like
*Core repository not found. Set ZENZIC_CORE_PATH or place the core repo as a sibling.*

**Cause:** The Shared Sovereign Verification Model resolves the core repository via a
priority chain:

1. `ZENZIC_CORE_PATH` environment variable (explicit override)
2. `./_zenzic_core` (CI canonical path)
3. `../zenzic` (sibling layout — recommended for local development)

None of these resolved to a valid core repository.

**Resolution:**

- **Sibling layout (recommended):** Place the repositories as siblings:

  ```text
  workspace/
    zenzic/
    zenzic-doc/
    zenzic-action/
  ```

  Then run `just verify` from `zenzic-doc` or `zenzic-action` — the resolver finds
  `../zenzic` automatically.

- **Explicit override:** If the core repository is in a non-standard location:

  ```bash
  ZENZIC_CORE_PATH=/absolute/path/to/zenzic just verify
  ```

Do not suppress this error with a config workaround — it indicates a setup misconfiguration.

---

## Release Workflow

### `just release` fails with "release-contracts" error

**Symptom:** `just release patch` (or `minor`/`major`) exits with:

```text
release-contracts failed: ...
```

**Cause:** The `release-contracts` recipe enforces architectural invariants before
allowing a version bump. Common violations:

| Error message | Cause | Fix |
|:---|:---|:---|
| `release part must not use --allow-dirty` | `--allow-dirty` flag present in the `release part` recipe | Remove the flag — the working tree must be clean |
| `release part must not create tags` | A `git tag` call was introduced in the release recipe | Tags are created by the CI workflow, not locally |
| `all git commits must use DCO (-s) and GPG signing (-S)` | Commit command in recipe missing `-s -S` | Add both flags to every `git commit` call in the recipe |

**Resolution:** Fix the offending line in the `justfile` recipe and re-run `just release-contracts` to verify before attempting the bump again.

---

## Common Zenzic Blocks

Review the common diagnostic signals and troubleshooting resolution steps detailed below.

### Z105 Absolute Path Detected

**Symptom:** Zenzic reports `[Z105] absolute path '...' found` for a link that starts with `/`.

**Why it matters:** an absolute, site-root-relative link (e.g. `/guide`) is
resolved from the server root. On a site hosted under a subdirectory (a
GitHub Pages project site, a CDN subdirectory deployment), `/guide` resolves
to the wrong URL — the link silently breaks in that hosting context even
though it works locally.

**Standard resolution:** Prefer relative paths (for example `../guide.md` or
`guide.md`) over absolute site-root paths. Relative links resolve correctly
regardless of where the site is hosted.

**Validated exception:** Use inline suppression only when the absolute path is reviewed and
intentional. The directive must be placed at the **end of the same line** as the link —
not on the line above it, which silently fails to match (see
[Suppression Policy](../../reference/suppression-policy.md)):

```html
[Jump to appendix](/static/appendix/reference.pdf) <!-- zenzic:ignore: Z105 - fixed CDN-root asset path, not a page route -->
```

For a prefix that legitimately needs to stay absolute across many links (for example, every
link into a fixed CDN asset root), declare it once in `.zenzic.toml` instead of suppressing
each link individually, via [`absolute_path_allowlist`](../../reference/configuration-reference.md#absolute-path-allowlist):

```toml title=".zenzic.toml"
# Declare a fixed CDN-root asset prefix that is intentionally absolute,
# not a page route.
absolute_path_allowlist = ["/static/"]
```

Zenzic's own `Z112` (`STALE_ALLOWLIST_ENTRY`) keeps this list honest — an
allowlist prefix that no scanned link actually uses is flagged so the
exception doesn't silently outlive its reason.

Zenzic's own `Z112` (`STALE_ALLOWLIST_ENTRY`) keeps this list honest — an
allowlist prefix that no scanned link actually uses is flagged so the
exception doesn't silently outlive its reason.

---

> For release workflow details, see the
> [Developer Release and Governance Protocol](./release-governance-protocol.md).
> For the Shared Sovereign Verification Model, see
> [Sovereign Verification Model](../explanation/sovereign-verification-model.md).
