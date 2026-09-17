---
description: "How to scaffold and initialize a new Zenzic configuration file."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Initialize Configuration

For most projects, no configuration file is needed. Run `zenzic check all` and Zenzic will locate
the repository root via `.git` or `.zenzic.toml` and apply sensible defaults. If no `.zenzic.toml`
is found, Zenzic prints a Helpful Hint panel suggesting `zenzic init`.

Use `zenzic init` to scaffold the file automatically. It detects the documentation engine from the
project root (e.g. `mkdocs.yml`) and pre-sets `engine` in `[build_context]`:

```bash
zenzic init             # creates .zenzic.toml with detected engine
zenzic init --pyproject # embeds [tool.zenzic] in pyproject.toml instead
```

`--force` is not supported for configuration initialization — re-running `zenzic init` against an
existing file exits with an error. Edit `.zenzic.toml` (or `.zenzic.local.toml`) directly to modify
existing settings.

When `pyproject.toml` exists, `zenzic init` asks whether to embed the configuration there
as a `[tool.zenzic]` table.  Pass `--pyproject` to skip the interactive prompt.

## Interactive mode

`zenzic init --interactive` (or `-i`) asks before it writes, and asks only what the generated
file cannot decide for you:

1. **The engine.** The prompt offers every engine the adapter registry holds and proposes the
   one detected from the project root, saying why — `mkdocs.yml` found, `zensical.toml` found,
   or no engine file at all, in which case the proposal is `standalone`. Press Enter to accept
   the detection, or type another name.
2. **Each opt-in finding code, one at a time.** These are the codes that run only when their
   flag is set — `enable_circular_link_check` and the others. The list comes from the code
   registry, so a code added in a later release appears in the prompt without anyone editing
   `init`. Every answer defaults to *no*, and a *yes* writes `= true` for that flag in the
   generated `[policies]` section.
3. **Whether to embed in `pyproject.toml`**, when that file exists — the same question the
   plain command asks.

The **data-gated codes** are not asked. They are not off: they run as soon as their
`[policies]` data is declared, and "list your forbidden domains" is not a yes-or-no question.
The prompt prints which codes these are, and the generated file names each of them with the
key it waits on — both derived from the registry, so this page does not carry a list that
would go stale.

Without `--interactive` nothing about codes or engines is asked, so scripts and CI get exactly
what they get today: the detected engine, every opt-in flag written as `false`, and the
`pyproject.toml` question only when that file exists (pass `--pyproject` to pre-answer it).
Answering every interactive question with its default produces the same file as the plain
command.

When you need to customise behaviour — for example, to raise the word-count threshold for concise
technical reference pages, or to add team-specific placeholder patterns — create or edit
`.zenzic.toml` at the repository root:

```toml
# .zenzic.toml — minimal starting point

# Uncomment and adjust the fields you need
# Everything is optional. Absent fields use their defaults

# docs_dir = "docs"
# excluded_dirs = ["includes", "stylesheets", "overrides"]
# excluded_assets = []
# snippet_min_lines = 1
# placeholder_max_words = 50
# placeholder_patterns = ["coming soon", "work in progress", "wip", "todo", "stub"]

# [policies]
# required_frontmatter_keys = []   # Enforce YAML frontmatter metadata keys (Z610)
# forbidden_external_domains = []  # Restrict forbidden external link domains (Z611)

# [build_context]           # required only for folder-mode multi-locale projects
# engine         = "mkdocs" # "mkdocs" or "zensical"
# default_locale = "en"
# locales        = ["it"]   # non-default locale directory names
```

---

## See Also

- [Configuration Loading](../explanation/configuration-loading.md)
