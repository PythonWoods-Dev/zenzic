---
description: "Configure Z204 FORBIDDEN_TERM to block confidential terms from appearing in public documentation."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Configure the Privacy Gate

Z204 (`FORBIDDEN_TERM`) blocks confidential internal terms — project codenames, internal
hostnames, staging URLs — from leaking into public documentation.

---

## Architecture

The Privacy Gate uses a two-file model:

| File | Purpose | Committed? |
|:-----|:--------|:-----------|
| `.zenzic.toml` | Shared project configuration | Yes |
| `.zenzic.local.toml` | Machine-local forbidden patterns | **No** |

`forbidden_patterns` lives exclusively in `.zenzic.local.toml`. This file is never committed.
Zenzic enforces this by automatically adding `.zenzic.local.toml` to `.gitignore` on `zenzic init`.

---

## Setup

Follow the setup instructions below to configure your development and scanning environment.

### 1. Initialise the local overlay

If `.zenzic.local.toml` does not yet exist, create it via:

```bash
zenzic init
```

This creates `.zenzic.local.toml` and adds it to `.gitignore` automatically.

### 2. Add forbidden patterns

Open `.zenzic.local.toml` and populate the `forbidden_patterns` list:

```toml
[governance]
forbidden_patterns = [
    "CODENAME-PHOENIX",
    "internal-staging.example.corp",
    "acme-internal-api",
]
```

Patterns are matched as literal strings, case-insensitive. RE2 DFA syntax is supported
for patterns that require regex matching — see the [Configuration Reference](../reference/configuration-reference.md)
for the full `forbidden_patterns` specification.

### 3. Verify `.gitignore`

Confirm `.zenzic.local.toml` is protected:

```bash
git check-ignore -v .zenzic.local.toml
# expected: .gitignore:N:.zenzic.local.toml .zenzic.local.toml
```

If the line is absent, add it manually:

```bash
echo ".zenzic.local.toml" >> .gitignore
```

### 4. Run the check

```bash
zenzic check all
```

Z204 fires with exit code 2 when any forbidden term is found. Exit code 2 is identical to
Z201 (credential exposure) — the score collapses to 0 unconditionally (Security Override).

---

## CI integration

In CI, `forbidden_patterns` is typically empty — no `.zenzic.local.toml` is checked out.
Z204 therefore does not fire in CI unless you explicitly provision patterns via a CI secret:

```yaml
# GitHub Actions example
- name: Write local zenzic overlay
  run: |
    cat > .zenzic.local.toml << 'EOF'
    [governance]
    forbidden_patterns = ${{ secrets.ZENZIC_FORBIDDEN_PATTERNS }}
    EOF
```

Alternatively, pass patterns at runtime using the `--forbidden` flag (if available in your
Zenzic version) rather than writing a file.

---

## Precedence

Configuration is resolved in the following order (later entries override earlier):

1. `.zenzic.toml` — shared project defaults
2. `pyproject.toml [tool.zenzic]` — embedded alternative to `.zenzic.toml`
3. `.zenzic.local.toml` — machine-local overlay (additive merge for list fields)

For `forbidden_patterns`, the overlay is **additive**: patterns in `.zenzic.local.toml`
are appended to any patterns declared in `.zenzic.toml`. They do not replace them.

---

## Related

- [Configuration Reference](../reference/configuration-reference.md) — full `forbidden_patterns` field specification
- [Configuration Strategy](./configuration-strategy.md) — troubleshooting the two-file model
- [Examples Overview](../tutorials/examples/index.md) — runnable Z-code gallery scenarios
