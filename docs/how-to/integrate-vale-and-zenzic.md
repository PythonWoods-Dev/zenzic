---
description: "Wire Vale and Zenzic into the same pre-commit pass, each reading its own config file and gating independently."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Integrate Vale and Zenzic in the Same Pre-Commit Pass

Zenzic checks documentation structure and security: broken links, orphan
pages, path traversal, leaked credentials. This guide wires it into the same
`.pre-commit-config.yaml` as an existing Vale setup, so a single commit is
gated on both, in one pass, with no shared configuration and no ordering
dependency between them.

For what Vale itself checks, how it evaluates a rule, or what its output and
exit codes mean, see
[Vale's own documentation](https://vale.sh/docs/) — this guide covers only
the mechanics of running the two together, not Vale's behavior.

---

## Why run both, not one

Zenzic and Vale read different config files and report different finding
classes — this guide's `.zenzic.toml` and `.vale.ini` examples below share no
keys and no schema. Running only one tool leaves the other's finding classes
unchecked by construction: nothing configured on Zenzic's side inspects
prose, and nothing configured on Vale's side inspects links, credentials, or
navigation structure.

---

## Prerequisites

- Vale installed and a `.vale.ini` already configured. Vale's own
  installation, configuration, and license terms are out of scope here — see
  [Vale's own documentation](https://vale.sh/docs/) for that step.
- Zenzic installed — see [Installation & Environment](install.md) if you have
  not done this yet.
- A `.zenzic.toml` at the repository root — see
  [Initialize Configuration](initialize-configuration.md).

---

## Step 1 — Confirm both config files coexist

Each tool reads only its own file:

```toml title=".zenzic.toml"
[build_context]
engine = "mkdocs"   # or "zensical", "standalone" — see configure-adapter.md
```

```ini title=".vale.ini"
StylesPath = styles
MinAlertLevel = warning
Packages = Google

[*.md]
BasedOnStyles = Google
```

The `.vale.ini` example above is a starting point for wiring the hook in
Step 2 — configuring `StylesPath`, `Packages`, and rule levels for your
project is Vale's own setup step; see its documentation for what each key
does and how to verify the configuration is complete before relying on it.

## Step 2 — Add both hooks to `.pre-commit-config.yaml`

```yaml title=".pre-commit-config.yaml"
repos:
  # Prose style
  - repo: https://github.com/vale-cli/vale
    rev: v3.20.0  # pin to your evaluated version — verify the current tag before use
    hooks:
      - id: vale

  # Structural integrity & security
  - repo: local
    hooks:
      - id: zenzic
        name: Zenzic — structural integrity & security gate
        entry: uvx zenzic check all --strict
        language: system
        files: \.(md|mdx)$
        pass_filenames: false
```

Both hooks run on every commit touching Markdown. Zenzic's hook here reads
only its own `.zenzic.toml` and reports only Zenzic's own finding codes;
whether or how the Vale hook's exit code responds to a given finding is
governed by Vale's own configuration, not by anything in this file.

## Step 3 — Verify the Zenzic gate fires

Confirm the Zenzic hook actually blocks on a real structural defect, not just
that the config parses. Zenzic locates its repository root from a
`.zenzic.toml`, `.git`, or engine config file in an ancestor directory, so
run this from inside your actual project:

```bash
# Zenzic should fail on a structural defect
echo "[broken](./does-not-exist.md)" > docs/zenzic-check.md
uvx zenzic check links docs/zenzic-check.md   # expect: Z101, exit 1
rm docs/zenzic-check.md
```

Verify the Vale hook the same way, against your own `.vale.ini` and rule
configuration — see Vale's documentation for how to construct a case that
fails under your configured `MinAlertLevel`. Each hook's pass/fail behavior
depends only on its own tool and its own config file; verifying one does not
verify the other.

## Step 4 — CI parity

Mirror the same two steps in CI, so a locally-installed-but-not-run hook (see
[CI/CD Quality Gates](configure-ci-cd.md#local-quality-gate) for why that gap
matters) does not become the only enforcement point:

```yaml title=".github/workflows/ci.yml"
- name: Vale
  uses: vale-cli/vale-action@v3  # org renamed from errata-ai — verify current org/tag before use

- name: Zenzic (structure & security)
  run: uvx zenzic check all --strict --ci
```

---

## Terser Zenzic output

Zenzic's default text output prints one summary line per finding
(`path:line  marker  [code]  message`); a multi-line quoted snippet is added
only for hard-error-severity findings, not warnings. Two flags trim this
further:

- `--no-header` drops the startup banner, keeping every per-finding line.
- `--quiet`/`-q` drops per-finding output entirely, printing only an
  aggregate count (`zenzic: 1 error(s), 3 warning(s)`) — useful for a
  pass/fail check, not for reading individual findings.

For machine consumption rather than terminal reading, `--format
github-annotations` emits one line per finding in GitHub's workflow-command
syntax.

---

## What this does not do

This guide does not configure Vale's rules, and Zenzic does not read Vale's
configuration or its findings — the two tools' config files and finding
codes are entirely disjoint. `Z518`/`Z519` are Zenzic's own lightweight,
RE2-based passive-voice and weasel-word heuristics; whether they overlap with
any rule in your configured Vale style is a property of that style's own
rules, not something this guide asserts either way. Configuring Vale's own
rule set is entirely Vale's own setup step, covered in its documentation.
