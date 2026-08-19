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
zenzic init --force     # overwrite an existing file
```

When `pyproject.toml` exists, `zenzic init` asks whether to embed the configuration there
as a `[tool.zenzic]` table.  Pass `--pyproject` to skip the interactive prompt.

When you need to customise behaviour — for example, to raise the word-count threshold for concise
technical reference pages, or to add team-specific placeholder patterns — create or edit
`.zenzic.toml` at the repository root:

```toml
# .zenzic.toml — minimal starting point

# Uncomment and adjust the fields you need
# Everything is optional. Absent fields use their defaults

# docs_dir = "docs"
# excluded_dirs = ["includes", "assets", "stylesheets", "overrides"]
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
