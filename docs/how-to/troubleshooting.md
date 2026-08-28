<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Troubleshooting

Quick reference for the most common Zenzic problems.
Each entry follows the pattern: **Symptom → Cause → Resolution**.

For the full configuration model, see the [Configuration Reference](../reference/configuration-reference.md).
For the complete list of finding codes, see [Finding Codes](../reference/finding-codes.md).

---

## Editor Integration

This section details the specifications and guidelines for Editor Integration within the Zenzic ecosystem.

### `Zenzic: Not Found (ENOENT)`

**Symptom:** Status bar shows `$(error) Zenzic: Not Found` or prompt reads *Zenzic binary not found*.

**Cause:** The `zenzic` executable is not installed or not present in system `$PATH` / standard user directories (`~/.local/bin`, `~/.uv/bin`).

**Resolution:**

1. Install Zenzic in your project virtual environment (Track 2: `uv add --dev zenzic` or `pip install zenzic`), which the VS Code extension automatically discovers.
2. Or configure `zenzic.executablePath` in VS Code settings with the full path to your virtual environment binary (e.g., `/home/user/project/.venv/bin/zenzic`).
3. Or install as an isolated global tool (Track 3: `uv tool install zenzic`).

---

### `Zenzic: Outdated Core`

**Symptom:** Status bar shows `$(error) Zenzic: Outdated Core` or notification requests upgrading.

**Cause:** The installed Zenzic Core binary version is lower than the VS Code extension's
required minimum. The extension checks this at startup and reports the exact minimum it
needs directly in the error notification (`Zenzic extension requires Zenzic Core vX.Y.Z or
higher`) — that message is the live source of truth; this page does not repeat the number,
since it changes with every `zenzic-vscode` release and is not tracked by any version-bump
tooling shared with this documentation.

**Resolution:** Update the Zenzic executable to the latest version:

```bash
uv tool install --force zenzic
```

---

### Server Version Check Errors

**Symptom:** Notification reads *Could not verify Zenzic Core version*.

**Cause:** Executing `zenzic --version` returned an error or non-zero exit code.

**Resolution:** Verify that `zenzic --version` runs cleanly in your terminal and check permissions on `zenzic.executablePath`.

---

## Configuration

This section details the specifications and guidelines for Configuration within the Zenzic ecosystem.

### External link check is slow or needs suppression

External link validation (Pass 3) only runs under `--strict` (confirmed live: without `--strict`,
no network requests happen and a broken external link is not flagged at all). `--no-external`
additionally suppresses it even when `--strict` is passed — use it for air-gapped or offline
`--strict` runs.
To permanently suppress specific URLs without disabling external validation, add their prefixes to `excluded_external_urls` in `.zenzic.toml`:

```toml title=".zenzic.toml"
excluded_external_urls = [
    "https://internal.company.com",
    "https://github.com/MyOrg/private-repo",
]
```

---

### `zenzic:ignore` does not suppress a Z2xx finding

Z2xx codes (`Z201`, `Z202`, `Z203`, `Z204`, `Z205`) are **non-suppressible**. They bypass the
suppression system entirely. The `zenzic:ignore` directive has no effect on these codes.

**Resolution:** Remove the content that triggers the finding. There is no configuration
flag to disable Z2xx rules.

---

### Forbidden pattern declared in `.zenzic.local.toml` is not detected

Possible causes:

| Cause | Diagnostic | Fix |
|:------|:-----------|:----|
| File not found | `zenzic config explain` → check `forbidden_patterns` list | Verify path: `.zenzic.local.toml` must be in the repo root |
| Pattern uses PCRE syntax | Pattern silently not matched | Use RE2 DFA syntax. Lookaheads and backreferences are not supported |
| File is git-ignored and not present in CI | Z204 only fires locally | Provision patterns via CI secret (see [Privacy Gate](./configure-privacy-gate.md)) |

---

### Files that should be excluded are still scanned

`excluded_dirs` and `excluded_file_patterns` in `.zenzic.toml` apply only to documentation
source files. They do not interact with `.gitignore`.

**System-excluded paths** (never need to be declared):

- Build output: `build/`, `dist/`, `temp/`, `tmp/`, `.tox/`, `mutants/`
- Toolchain: `.git/`, `.venv/`, `node_modules/`
- Config files: `*.toml`, `*.yaml`, `*.json`, `*.lock`, `Makefile`, `justfile`

Only repo-specific entries not in the system exclusion list belong in `excluded_dirs`.

---

### `fail_under` threshold not respected

`fail_under` applies to the **Documentation Quality Score (DQS)**, not to individual
finding counts. A score of 0 from the Security Override does not by itself force an exit
code above 1 — the real security-breach codes (`Z201`, `Z204`, `Z205`) already exit 2 on
their own via the credential-scanner bridge, and `Z203` exits 3, independent of `fail_under`.
`Z202` is the one Z2xx code that deliberately stays at a plain exit 1.

Verify the effective threshold and where it's set:

```bash
zenzic config explain
```

---

### Score is 0 but no credentials are present

Z204 (`FORBIDDEN_TERM`) also triggers the Security Override. Run `zenzic check all` — every
`Z204` finding is printed by default, with the matched line and file:

Look for `Z204` in the output. If `forbidden_patterns` in `.zenzic.local.toml` matches
content in your documentation, the score collapses to 0.

---

### Local override not applied in CI

`.zenzic.local.toml` is git-ignored and not present in CI checkouts by default.
This is expected. To apply overrides in CI, write the file from a secret before running Zenzic:

```yaml
- name: Write local zenzic overlay
  env:
    FORBIDDEN: ${{ secrets.ZENZIC_FORBIDDEN_PATTERNS }}
  run: printf '[governance]\nforbidden_patterns = %s\n' "$FORBIDDEN" > .zenzic.local.toml
```

---

### Disable network cache in ephemeral environments

Zenzic caches external link responses for 24 hours by default. In highly ephemeral environments (like certain Dockerized CI pipelines) where persisting `.zenzic_cache/` between runs is impossible or undesirable, you can disable the cache entirely to force synchronous network validation on every run.

```toml title=".zenzic.toml"
[network]
cache_ttl_hours = 0
```

---

### Handling Build-Time Artifacts

Links pointing to files generated *during* the site build (e.g., `rss.xml` generated by MkDocs plugins) will trigger `Z104 (File Not Found)` because Zenzic scans the source, not the build output.

Do not use absolute production URLs (e.g., `https://domain.com/rss.xml`) to bypass this, as it breaks air-gapped portability. Instead, use relative links within raw HTML tags and suppress the specific node using the parameterless `data-zenzic-ignore` attribute.

*Example:*

```html
<a href="../rss.xml" data-zenzic-ignore>RSS Feed</a>
```

---

> For the full field specification, see [Configuration Reference](../reference/configuration-reference.md).
