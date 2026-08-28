---
description: "The Agnostic Citizen configuration chain and file priority logic."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Configuration Loading

Zenzic follows a three-level **Agnostic Citizen** priority chain when searching for configuration
at startup:

| Priority | Source | When used |
| :---: | :--- | :--- |
| 1 | `.zenzic.toml` at repository root | Always preferred — the authoritative sovereign config |
| 2 | `[tool.zenzic]` in `pyproject.toml` | Used only when `.zenzic.toml` is absent |
| 3 | Built-in defaults | Used when neither file is present |

The repository root is located by walking upward from the current working directory until a `.git`
directory, a `.zenzic.toml`, a `zensical.toml`, or an `mkdocs.yml` is found. `pyproject.toml` is not
itself a root marker — it is read only once the root is already located by one of these markers.

---

## .zenzic.toml (Priority 1)

The dedicated configuration file. If it exists, Zenzic reads it and ignores `pyproject.toml`
entirely — there is no merging between the two files.

### pyproject.toml (Priority 2)

Python projects that already have a `pyproject.toml` can embed Zenzic configuration in the
`[tool.zenzic]` table, eliminating the need for a separate file:

```toml
# pyproject.toml — embed Zenzic config in the standard Python metadata file

[tool.zenzic]
docs_dir   = "docs"
fail_under = 90

[tool.zenzic.build_context]
engine = "mkdocs"

[[tool.zenzic.custom_rules]]
id       = "ZZ-NODRAFT"
pattern  = "(?i)\\bDRAFT\\b"
message  = "Remove DRAFT marker before publishing."
severity = "warning"
```

All fields supported in `.zenzic.toml` are equally supported in `[tool.zenzic]`. The
`[build_context]` sub-table becomes `[tool.zenzic.build_context]`, and `[[custom_rules]]` arrays
become `[[tool.zenzic.custom_rules]]`.

!!! note "Sovereignty rule"
    If both `.zenzic.toml` **and** `pyproject.toml` exist in the repository root, `.zenzic.toml`
    wins unconditionally. The `[tool.zenzic]` table in `pyproject.toml` is ignored.

### Error handling

If the winning config file contains a **TOML syntax error**, Zenzic raises a `ConfigurationError`
with a human-friendly message and exits immediately — silent fallback on a broken config file
would hide mistakes. Unknown fields are silently ignored, which means adding fields not yet
supported by your installed version is safe.

---

## See Also

- [Initialize Configuration](../how-to/initialize-configuration.md)
